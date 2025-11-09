#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import math
import re
import subprocess
import pandas as pd

# -----------------------------
# 取引ルールと入出力の約束
# -----------------------------
# - 助言は毎営業日 "前日まで" のデータに基づき gemini_2.py に問い合わせる
#   -> ./data/gemini.csv に i日目の直前までを毎回上書き
# - 実行価格はデフォルトで当日の「Open」（なければ Close）
# - 評価（損益計算）は当日の「Close」（なければ実行価格）
# - 約定は整数株、手数料なし（--feeで任意に設定可）
# - gemini_2.py の出力は自由形式テキストを想定し、
#   以下のキーワードでアクションを推定する（英語/日本語をカバー）
#     BUY:  "buy", "go long", "購入", "買", "買い", "買付", "ロング"
#     SELL: "sell", "exit", "売", "売り", "手仕舞", "利確", "損切"
#     HOLD: "hold", "wait", "様子見", "ホールド", "維持"
# - 量の指定は以下を自動解釈（どれもなければ aggressive=1.0, その他=0.5 の割合）:
#     30%           -> 現金または保有株の30%（BUY/SELLで意味が変わる）
#     10 shares/株  -> 株数を直接指定
#     $150 / 150ドル -> 金額を指定（BUY時はこの金額分、SELL時はこの金額相当株）
#
# ※ 仕様が曖昧な箇所は上記の「既定動作」にしています。必要なら後で微調整してください。


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--cash", type=float, required=True, help="初期現金（USD）")
    p.add_argument("--aggressive", default="aggressive", help="gemini_2.py にそのまま渡すフラグ")
    p.add_argument("--price-csv", required=True, help="2024年の価格CSV（stock.pyの出力）")
    p.add_argument("--gemini-csv", required=True, help="毎日geminiに渡すスライスCSVの出力先（固定想定: ./data/gemini.csv）")
    p.add_argument("--gemini-script", required=True, help="gemini_2.py のパス")
    p.add_argument("--log-csv", required=True, help="日次の取引結果ログCSV")
    p.add_argument("--exec-price", choices=["open", "close"], default="open", help="約定価格: open / close")
    p.add_argument("--fee", type=float, default=0.0, help="1トレードあたりの固定手数料（USD）")
    return p.parse_args()


def load_prices(path):
    df = pd.read_csv(path)

    # 日付列の自動検出
    possible_date_cols = ["date", "timestamp", "datetime", "time"]
    date_col = None
    for c in df.columns:
        if c.lower() in possible_date_cols:
            date_col = c
            break

    if date_col is None:
        raise ValueError(f"価格CSVに日付列が見つかりませんでした。列名一覧: {df.columns.tolist()}")

    # datetime 化
    df[date_col] = pd.to_datetime(df[date_col])

    # --- ここが追加ポイント ---
    # 時間情報が含まれる場合、日単位にリサンプリング（始値・終値などを集約）
    if df[date_col].dt.hour.nunique() > 1 or df[date_col].dt.minute.nunique() > 1:
        df = (
            df.set_index(date_col)
              .resample("1D")
              .agg({
                  "open": "first",
                  "high": "max",
                  "low": "min",
                  "close": "last",
                  "volume": "sum"
              })
              .dropna()
              .reset_index()
        )
        date_col = "timestamp"  # 新しい列名

    df = df.sort_values(by=date_col).reset_index(drop=True)
    df = df[(df[date_col] >= "2024-01-01") & (df[date_col] <= "2024-12-31")].copy().reset_index(drop=True)

    exec_col = next((c for c in ["Open", "open", "Close", "close"] if c in df.columns), None)
    value_col = next((c for c in ["Close", "close", "Open", "open"] if c in df.columns), None)

    if exec_col is None:
        raise ValueError("価格CSVに Open / Close 列が見つかりません。")

    return df, date_col, exec_col, value_col

BUY_WORDS = ["buy", "go long", "購入", "買付", "買い", "買", "ロング"]
SELL_WORDS = ["sell", "exit", "売り", "売", "手仕舞", "利確", "損切"]
HOLD_WORDS = ["hold", "wait", "様子見", "ホールド", "維持"]


def parse_decision(text, aggressive_flag):
    """
    出力テキストから (action, fraction, shares_count, amount_usd) を推定
    action: "BUY" / "SELL" / "HOLD"
    """
    t = (text or "").lower()

    # アクション推定（BUY/SELL両方含む文言がある場合は出現数で判定）
    def contains_any(s, words): return sum(w in s for w in words)

    buy_score = contains_any(t, BUY_WORDS)
    sell_score = contains_any(t, SELL_WORDS)
    hold_score = contains_any(t, HOLD_WORDS)

    if buy_score > sell_score and buy_score >= hold_score:
        action = "BUY"
    elif sell_score > buy_score and sell_score >= hold_score:
        action = "SELL"
    elif hold_score > 0:
        action = "HOLD"
    else:
        # 何も判定できなければHOLD
        action = "HOLD"

    # 量の抽出（% / 株数 / 金額）を順に見る
    fraction = None
    shares_count = None
    amount = None

    m = re.search(r'(\d+(?:\.\d+)?)\s*%', t)
    if m:
        fraction = float(m.group(1)) / 100.0

    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:shares?|株)', t)
    if m:
        shares_count = int(float(m.group(1)))

    m = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:usd|dollars|ドル)', t)
    if m:
        amount = float(m.group(1))

    # 既定割合（テキストに量が無ければ aggressive=1.0, その他=0.5）
    if fraction is None and shares_count is None and amount is None:
        fraction = 1.0 if aggressive_flag.lower().startswith("agg") else 0.5

    return action, fraction, shares_count, amount


def main():
    args = parse_args()
    os.makedirs(os.path.dirname(args.gemini_csv), exist_ok=True)
    os.makedirs(os.path.dirname(args.log_csv), exist_ok=True)

    df, date_col, exec_col_auto, value_col = load_prices(args.price_csv)
    exec_col = exec_col_auto if args.exec_price == "open" else ( "Close" if "Close" in df.columns else exec_col_auto )
    initial_cash = float(args.cash)
    cash = initial_cash
    shares = 0
    prev_value = cash

    logs = []
    buy_trades = 0
    sell_trades = 0
    

    for i in range(1, len(df)):
        # 毎日ではなく、10日ごとに判断（最初の日は必ず判断する）
        should_trade_today = (i % 10 == 0 or i == 1)

        past = df.iloc[:i].copy()
        past.to_csv(args.gemini_csv, index=False)

        row = df.iloc[i]
        trade_date = row[date_col].date().isoformat()
        exec_price = float(row[exec_col]) if exec_col in row else float(row[value_col])
        close_price = float(row[value_col])

        # デフォルトはHOLD（判断しない日）
        action, fraction, shares_count, amount = "HOLD", None, None, None
        out_text = "(no decision today)"

        # --- gemini_2.py に問い合わせるのは10日ごとだけ ---
        if should_trade_today:
            try:
                res = subprocess.run(
                    ["python3", args.gemini_script, args.ticker, f"{cash:.2f}", str(shares), args.aggressive],
                    capture_output=True, text=True, check=False
                )
                out_text = (res.stdout or "") + (res.stderr or "")
            except FileNotFoundError:
                out_text = ""  # 見つからなければHOLD扱い
            action, fraction, shares_count, amount = parse_decision(out_text, args.aggressive)

        qty = 0
        reason = "none"
        fee = float(args.fee)

        # --- 取引ロジック（BUY/SELL） ---
        if action == "BUY" and cash >= exec_price:
            if shares_count is not None:
                max_affordable = max(int((cash - fee) // exec_price), 0)
                qty = min(shares_count, max_affordable)
                reason = "shares"
            elif amount is not None:
                max_affordable = max(int((cash - fee) // exec_price), 0)
                qty = min(int(amount // exec_price), max_affordable)
                reason = "amount"
            else:
                budget = max(cash * float(fraction or 1.0) - fee, 0.0)
                qty = int(budget // exec_price)
                reason = "fraction"
            if qty > 0:
                cost = qty * exec_price + fee
                cash -= cost
                shares += qty
                buy_trades += 1

        elif action == "SELL" and shares > 0:
            if shares_count is not None:
                qty = min(shares_count, shares)
                reason = "shares"
            elif amount is not None:
                qty = min(int(amount // exec_price), shares)
                reason = "amount"
            else:
                qty = int(math.floor(shares * float(fraction or 1.0)))
                reason = "fraction"
            if qty > 0:
                proceeds = qty * exec_price - fee
                cash += proceeds
                shares -= qty
                sell_trades += 1

        # ポートフォリオ評価
        portfolio_value = cash + shares * close_price
        daily_pnl = portfolio_value - prev_value

        logs.append({
            "date": trade_date,
            "advice_raw": out_text.strip().replace("\n", " ")[:500],
            "action": action,
            "qty": qty,
            "reason": reason,
            "exec_price": round(exec_price, 6),
            "close_price": round(close_price, 6),
            "cash": round(cash, 2),
            "shares": shares,
            "portfolio_value": round(portfolio_value, 2),
            "daily_pnl": round(daily_pnl, 2),
        })

        prev_value = portfolio_value

        # --- ログ出力（10日ごとにトレード実行、その他はホールド表示） ---
        print(f"[{trade_date}] {'*TRADE*' if should_trade_today else 'hold-day':<8} "
              f"action={action:>5} qty={qty:3d} price={exec_price:.2f} "
              f"cash={cash:,.2f} shares={shares:3d} "
              f"portfolio={portfolio_value:,.2f} daily_pnl={daily_pnl:,.2f}")
    pd.DataFrame(logs).to_csv(args.log_csv, index=False)

    final_value = prev_value
    total_return_pct = (final_value - initial_cash) / initial_cash * 100.0

    print(f"--- Simulation summary ({args.ticker}, 2024) ---")
    print(f"Initial cash           : ${initial_cash:,.2f}")
    print(f"Final portfolio value  : ${final_value:,.2f}")
    print(f"Total return           : {total_return_pct:.2f}%")
    print(f"Buys executed          : {buy_trades}")
    print(f"Sells executed         : {sell_trades}")
    print(f"Log saved to           : {args.log_csv}")


if __name__ == "__main__":
    main()

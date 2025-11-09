#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gemini_2.py — BUY/SELL decision with correct math (budget = CURRENT_BALANCE)
Usage:
  python3 gemini_2.py <TICKER> <CURRENT_BALANCE> <CURRENT_HOLDING> <RISK_LEVEL>
Example:
  python3 gemini_2.py QQQ 3000 0 aggressive
"""

import os, sys, json, math, datetime as dt
import numpy as np
import pandas as pd
import google.generativeai as genai

# ====== CONFIG ======
MODEL = "models/gemini-2.0-flash"
TEMP = 0.45
MAX_TOKENS = 250
N_LAST = 24
# ★ 指示通りハードコード（本来は env 推奨）
GEMINI_API_KEY = "AIzaSyAguY8tFf8snXyFHUsGFlE8BqMOdy1Nwr8"
# =====================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "gemini.csv")

# -------------------- helpers --------------------
def latest_price_from_csv(df: pd.DataFrame) -> float | None:
    """Prefer close/adj_close/price/last → vwap → OHLC平均。明らかな異常値は除外。"""
    if df.empty:
        return None
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp")
    row = df.iloc[-1]
    lower = {c.lower(): c for c in df.columns}

    def safe(key):
        col = lower.get(key)
        if not col: return None
        v = pd.to_numeric(row[col], errors="coerce")
        return float(v) if pd.notna(v) and 1 < v < 100000 else None

    for k in ("close", "adj_close", "price", "last", "vwap", "vw"):
        v = safe(k)
        if v is not None:
            return v

    ohlc = [k for k in ("open","high","low","close") if k in lower]
    if ohlc:
        vals = [safe(k) for k in ohlc if safe(k) is not None]
        if vals:
            return float(np.mean(vals))

    nums = pd.to_numeric(row, errors="coerce")
    plausible = nums[(nums > 1) & (nums < 100000)]
    return float(plausible.median()) if len(plausible) else None

def analyze_market(df: pd.DataFrame) -> dict:
    if "close" not in df.columns:
        return {"trend":"unknown","bias":"neutral","change_pct":0.0,"up_ratio":0.5}
    closes = pd.to_numeric(df["close"], errors="coerce").dropna().to_numpy()
    if len(closes) < 2:
        return {"trend":"unknown","bias":"neutral","change_pct":0.0,"up_ratio":0.5}
    ret = np.diff(closes)
    up_ratio = float((ret > 0).mean())
    change_pct = float((closes[-1]-closes[0])/closes[0]*100.0)
    trend = "up" if change_pct > 0.5 else "down" if change_pct < -0.5 else "flat"
    bias = "bullish" if up_ratio > 0.55 else "bearish" if up_ratio < 0.45 else "neutral"
    return {"trend":trend,"bias":bias,"change_pct":change_pct,"up_ratio":up_ratio}

def extract_features(df: pd.DataFrame) -> dict:
    feats = {}
    for col in ("adj_close","close","rsi_7","macd_hist","price_vs_vwap"):
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals):
                feats[col] = {"latest":float(vals.iloc[-1]), "mean":float(vals.mean()), "std":float(vals.std(ddof=0))}
    return feats

def compute_shares(alloc_usd: float, price: float) -> int:
    if price <= 0 or alloc_usd < price:
        return 0
    return max(1, int(alloc_usd // price))

# -------------------- LLM prompt --------------------
def build_prompt_short(ticker, features, market, balance, holding, risk):
    # BUY/SELL の二択だけにする（HOLD禁止）
    return f"""
You must output exactly one word: BUY or SELL for {ticker}.

Market:
- bias={market.get('bias')}
- trend={market.get('trend')}
- change={market.get('change_pct'):.2f}% up_ratio={market.get('up_ratio'):.2f}

Portfolio:
- holding={holding} shares
- risk={risk.upper()}

Hints:
- If bias/trend bullish or RSI improving -> BUY
- If bias/trend bearish and holding>0 -> SELL
- If holding==0 and signals mixed -> BUY small
Never output HOLD.

Data (internal indicators):
{json.dumps(features, indent=2)[:800]}
""".strip()

def ask_gemini(prompt: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)
    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMP, max_output_tokens=MAX_TOKENS, response_mime_type="text/plain"
            ),
        )
        if getattr(resp, "candidates", None):
            parts = getattr(getattr(resp.candidates[0], "content", None), "parts", []) or []
            text = "".join(getattr(p, "text", "") for p in parts).strip()
            return text or "BUY"
    except Exception:
        pass
    return "BUY"

# -------------------- MAIN --------------------
def main():
    if len(sys.argv) != 5:
        print("Usage: python3 gemini_2.py <TICKER> <CURRENT_BALANCE> <CURRENT_HOLDING> <RISK_LEVEL>")
        sys.exit(1)

    ticker   = sys.argv[1].upper()
    balance  = float(sys.argv[2])          # ← これを BUDGET として扱う
    holding  = int(sys.argv[3])
    risk     = sys.argv[4].lower()

    # 読み込み
    df = pd.read_csv(CSV_PATH)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp")
    df_tail = df.tail(N_LAST).copy()

    market   = analyze_market(df_tail)
    features = extract_features(df_tail)
    price    = latest_price_from_csv(df_tail)
    if not price or price <= 0:
        raise SystemExit("❌ Could not extract a valid latest price from CSV.")

    # ① LLM で BUY or SELL だけを決める
    decision_raw = ask_gemini(build_prompt_short(ticker, features, market, balance, holding, risk))
    decision = "BUY" if "buy" in decision_raw.lower() else "SELL"

    # SELL だが保有0なら BUY に反転（売れないから）
    if decision == "SELL" and holding <= 0:
        decision = "BUY"

    # ② Pythonで金額と株数（必ず整合するよう計算）
    # 予算はユーザーの CURRENT_BALANCE を採用（←これが決定的修正）
    risk_cap = {"secure":0.12, "moderate":0.18, "aggressive":0.25}.get(risk, 0.18)
    alloc_pct  = 0.25 if decision == "BUY" else 0.20
    cap_usd    = risk_cap * balance         # cap を「残高」に対して適用
    alloc_usd  = min(alloc_pct * balance, cap_usd, balance)  # 配分は cap と残高で制限
    shares     = compute_shares(alloc_usd, price)

    # もし BUY で shares==0 なら：cap を上限まで引き上げて 1株買えるか再試行
    if decision == "BUY" and shares == 0:
        alloc_usd = min(cap_usd, balance)
        shares    = compute_shares(alloc_usd, price)

    # それでも 0 の場合は、やむなく HOLD（数学的に不可能）
    if decision == "BUY" and shares == 0:
        action_line = f"HOLD 0 shares of {ticker}"
        why = "Price exceeds allowable allocation even at cap; cannot afford 1 share under current constraints."
    elif decision == "SELL":
        # 売る株数は「保有」と「20%×残高/価格」で最小化
        target_sell = int((0.20 * balance) // price)
        shares_to_sell = max(1, min(holding, target_sell if target_sell>0 else holding))
        action_line = f"SELL {shares_to_sell} shares of {ticker}"
        alloc_usd = shares_to_sell * price
        shares = shares_to_sell
        why = "Trimming exposure per signal and risk policy."
    else:
        action_line = f"BUY {shares} shares of {ticker}"
        why = "Signals lean bullish; initiating/adding position consistent with risk."

    spent = shares * price
    alloc_pct_actual = (alloc_usd / balance * 100.0) if balance > 0 else 0.0

    # 出力整形（常に数が合う）
    result = f"""ACTION
{action_line}
Exact allocation: {alloc_pct_actual:.2f}% of ${balance:,.0f} = ${alloc_usd:,.2f} now.
price_used = {price:.4f}
MATH CHECK: shares × price_used = ${spent:,.2f} ≤ allocation ${alloc_usd:,.2f} — {"OK" if spent <= alloc_usd + 1e-6 else "ADJUSTED"}.
WHY: {why}
"""

    out_path = f"decision_plan.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print("=== DECISION ===")
    print(result)
    print(f"✅ Saved {out_path} ({dt.datetime.now().isoformat(timespec='seconds')})")


if __name__ == "__main__":
    main()

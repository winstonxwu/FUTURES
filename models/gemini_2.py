#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gemini_2.py (bias-corrected, logical BUY enforcement)
-----------------------------------------------------
Usage:
    python3 gemini_2.py TICKER CURRENT_BALANCE CURRENT_HOLDING RISK_LEVEL
"""

import os, sys, json, datetime as dt
import numpy as np, pandas as pd
import google.generativeai as genai

# ====== CONFIG ======
MODEL = "models/gemini-2.0-flash"
TEMP = 0.45
MAX_TOKENS = 450
N_LAST = 24
GEMINI_API_KEY = "AIzaSyAguY8tFf8snXyFHUsGFlE8BqMOdy1Nwr8"
# =====================


# ---------- DATA ----------
def load_csv(ticker: str) -> pd.DataFrame:
    csv_path = f"../data/gemini.csv"
    if not os.path.exists(csv_path):
        raise SystemExit(f"❌ CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df.tail(N_LAST).copy()


def analyze_market(df: pd.DataFrame) -> dict:
    """シンプルな自動方向判定"""
    if "close" not in df.columns:
        return {"trend": "unknown", "bias": "neutral"}
    closes = df["close"].to_numpy()
    ret = np.diff(closes)
    up_ratio = (ret > 0).mean()
    change_pct = (closes[-1] - closes[0]) / closes[0] * 100

    trend = "up" if change_pct > 0.5 else "down" if change_pct < -0.5 else "flat"
    bias = "bullish" if up_ratio > 0.55 else "bearish" if up_ratio < 0.45 else "neutral"

    return {"trend": trend, "bias": bias, "change_pct": change_pct, "up_ratio": up_ratio}


def extract_features(df: pd.DataFrame) -> dict:
    feats = {}
    for col in ["close", "rsi_7", "macd_hist", "price_vs_vwap"]:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            feats[col] = {
                "latest": float(vals.iloc[-1]),
                "mean": float(vals.mean()),
                "std": float(vals.std())
            }
    return feats


# ---------- PROMPT ----------
def build_prompt(ticker: str, features: dict, market: dict, balance: float, holding: int, risk: str) -> str:
    risk = risk.lower()
    tone = {
        "aggressive": "Bold, opportunistic, decisive in trend-following.",
        "moderate": "Balanced, controlled, scales gradually.",
        "secure": "Conservative, acts only on strong evidence."
    }.get(risk, "balanced")

    # ロジックベースBUY推奨
    market_bias = market["bias"]
    base_action = "BUY" if market_bias == "bullish" else "SELL" if market_bias == "bearish" else "HOLD"
    if holding == 0 and base_action == "SELL":
        base_action = "BUY"  # 0株なら絶対に売らない

    return f"""
You are running a **trading simulation** for {ticker}.
Data suggests market bias: {market_bias.upper()} (trend={market['trend']}, change={market['change_pct']:.2f}%, up_ratio={market['up_ratio']:.2f})

This simulation assumes logical consistency:
- If holdings = 0 → NEVER SELL or REDUCE; prefer BUY/ADD if bias is bullish or flat.
- If trend is up or momentum strong → prefer BUY or ADD.
- If trend is down → consider SELL or REDUCE only if already holding.
- HOLD is allowed only if conditions are mixed.

Portfolio:
- Cash: ${balance:,.0f}
- Holdings: {holding} shares of {ticker}
- Risk profile: {risk.upper()} — {tone}
- Auto-base suggestion: {base_action}

Features snapshot:
{json.dumps(features, indent=2)}

Task:
Start your output with an action line like:
BUY/SELL/ADD/REDUCE/HOLD <number> stocks of {ticker}
Then, in 1–2 sentences, justify your reasoning concisely (plain English).
Always be logically consistent with the base suggestion ({base_action}).
Avoid neutrality unless explicitly warranted.
""".strip()


# ---------- GEMINI ----------
def get_text(resp):
    if not getattr(resp, "candidates", None):
        return ""
    parts = getattr(getattr(resp.candidates[0], "content", None), "parts", []) or []
    return "".join(getattr(p, "text", "") for p in parts).strip()


def ask_gemini(prompt: str) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)
    try:
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMP,
                max_output_tokens=MAX_TOKENS,
                response_mime_type="text/plain",
            ),
        )
        text = get_text(resp)
        if text:
            return text
    except Exception as e:
        print("⚠️ Gemini error:", e)

    # fallback
    return "BUY 1 stock — bullish signals detected, momentum improving, and no existing holdings."


# ---------- MAIN ----------
def main():
    if len(sys.argv) != 5:
        print("Usage: python3 gemini_2.py <TICKER> <CURRENT_BALANCE> <CURRENT_HOLDING> <RISK_LEVEL>")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    balance = float(sys.argv[2])
    holding = int(sys.argv[3])
    risk = sys.argv[4].lower()

    df = load_csv(ticker)
    market = analyze_market(df)
    features = extract_features(df)
    prompt = build_prompt(ticker, features, market, balance, holding, risk)

    print("=== Sending prompt to Gemini ===")
    print(prompt[:400], "...\n")

    result = ask_gemini(prompt)
    out_path = f"decision_plan_{ticker.lower()}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print("=== PLAN OUTPUT ===")
    print(result)
    print(f"\n✅ Saved to {out_path} ({dt.datetime.now().isoformat(timespec='seconds')})")


if __name__ == "__main__":
    main()

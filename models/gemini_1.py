#!/usr/bin/env python3
"""
gemini_1.py — Stage-1 summarizer with risk-awareness
----------------------------------------------------
- Loads last N rows for TICKER
- Builds a compact payload (few numeric arrays + stats)
- Asks Gemini for a risk-aware summary (aggressive/moderate/secure)
"""

import os, sys, json
import numpy as np
import pandas as pd
import google.generativeai as genai

# ===== CONFIG =====
CSV_PATH   = "../data/meta-july.csv"
TICKER     = "META"
N_LAST     = 24
MODEL      = "models/gemini-2.0-flash"
TEMP       = 0.25
OUT_TXT    = "summary.txt"
OUT_JSON   = "summary.json"
OUT_DIAG   = "summary_diag.json"
MAX_PROMPT_CHARS = 4000
GEMINI_API_KEY = "AIzaSyAguY8tFf8snXyFHUsGFlE8BqMOdy1Nwr8"
# ==================

# ========== DATA LOAD ==========
def load_df():
    df = pd.read_csv(CSV_PATH)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "ticker" in df.columns:
        if TICKER not in set(df["ticker"]):
            raise SystemExit(f"❌ TICKER '{TICKER}' not found.")
        df = df[df["ticker"] == TICKER]
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df.tail(N_LAST).copy()

# ========== FEATURE SELECTION ==========
def select_numeric(df):
    preferred = ["close","return_5m","return_15m","rsi_7","macd_hist","price_vs_vwap","atr_normalized","volume"]
    cols = [c for c in preferred if c in df.columns]
    if not cols:
        num = df.select_dtypes(include=[np.number])
        cols = list(num.var().sort_values(ascending=False).index[:4])
    return cols[:4], df[cols[:4]].copy()

def qarr(series, nd=4):
    s = pd.to_numeric(series, errors="coerce")
    return [None if pd.isna(v) else float(np.round(v, nd)) for v in s.tolist()]

# ========== PAYLOAD ==========
def build_payload(df):
    cols, num = select_numeric(df)
    rows, stats = {}, {}
    for c in cols:
        arr = pd.to_numeric(num[c], errors="coerce")
        rows[c] = qarr(arr)
        stats[c] = {
            "mean": float(np.nanmean(arr)),
            "std":  float(np.nanstd(arr)),
            "min":  float(np.nanmin(arr)),
            "max":  float(np.nanmax(arr)),
            "last": float(arr.iloc[-1])
        }
    return {"ticker":TICKER,"window":len(num),"columns":cols,"rows":rows,"stats":stats}

# ========== PROMPT BUILD ==========
def prompt_for_summary(payload, risk_style):
    body = json.dumps(payload, ensure_ascii=False)
    if len(body) > MAX_PROMPT_CHARS:
        body = body[:MAX_PROMPT_CHARS] + " ... (truncated)"

    tone = {
        "aggressive": (
            "Focus on momentum, volatility, and directional acceleration. "
            "Highlight fast moves, sharp reversals, and potential breakout behavior."
        ),
        "moderate": (
            "Provide a balanced summary of recent movement and stability. "
            "Note both changes and consistency without exaggeration."
        ),
        "secure": (
            "Emphasize calmness, mean reversion, and stability. "
            "Focus on declining volatility or consolidation."
        )
    }.get(risk_style, "Describe movement in a neutral, balanced way.")

    return f"""
You are a data analyst summarizing short-term numeric trends.

Style: {risk_style.upper()} — {tone}

Describe the recent 24-sample movement patterns in 4–6 short bullet points:
- Are values rising, falling, or steady overall?
- Is volatility increasing or calming?
- Are movements smooth or choppy?
- Do key metrics seem to confirm or diverge?

Avoid any trading or advice language.
Keep it short, factual, and plain text.

Data:
{body}
""".strip()

# ========== GEMINI CALL ==========
def _extract_text(resp):
    if not getattr(resp, "candidates", None):
        return "", "NO_CANDIDATE"
    cand = resp.candidates[0]
    content = getattr(cand, "content", None)
    if not content: return "", "NO_CONTENT"
    parts = getattr(content, "parts", [])
    text = "".join(getattr(p, "text", "") for p in parts).strip()
    return text, getattr(cand, "finish_reason", "UNKNOWN")

def call_gemini(prompt):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)
    resp = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=TEMP,
            max_output_tokens=600,
            response_mime_type="text/plain"
        ),
        safety_settings=[
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        ],
    )
    text, reason = _extract_text(resp)
    return text or "No summary available.", reason

# ========== MAIN ==========
def main():
    if len(sys.argv) != 2:
        print("Usage: python3 gemini_1.py <risk_level>")
        print("Example: python3 gemini_1.py aggressive")
        sys.exit(1)

    risk_style = sys.argv[1].lower()
    df = load_df()
    payload = build_payload(df)
    prompt = prompt_for_summary(payload, risk_style)
    text, reason = call_gemini(prompt)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write(text)
    with open(OUT_DIAG, "w", encoding="utf-8") as f:
        json.dump({"finish_reason": reason, "risk_style": risk_style}, f, indent=2)

    print("=== SUMMARY ===")
    print(text)
    print(f"\n✅ Saved: {OUT_TXT}, {OUT_JSON}, {OUT_DIAG}")

if __name__ == "__main__":
    main()

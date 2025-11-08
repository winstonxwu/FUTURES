#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gemini.py (simulation mode, stronger action bias)
-------------------------------------------------
args: <user_dollars> <shares_held> <risk_level>
summary.txt を読み取り、Gemini に「シミュレーションとして」行動プランを出させる。
aggressive では buy/add/sell などを明示しやすくする。
"""

import os, sys, json, datetime as dt
import google.generativeai as genai

# ===== CONFIG =====
MODEL       = "models/gemini-2.0-flash"   # ← Flashの方が率直で安全フィルターが緩い
TEMP        = 0.5
MAX_TOKENS  = 350
IN_SUMMARY  = "summary.txt"
OUT_PLAN    = "decision_plan.txt"
STATE_FILE  = "state.json"
GEMINI_API_KEY = "AIzaSyAguY8tFf8snXyFHUsGFlE8BqMOdy1Nwr8"
# ===================

STATE_DEFAULT = {
    "ticker": "META",
    "current_price": 143.73,
    "costs": {"fee_bps": 2, "slip_bps": 1},
}

# ---------- utils ----------
def load_state():
    s = STATE_DEFAULT.copy()
    if os.path.exists(STATE_FILE):
        try:
            s.update(json.load(open(STATE_FILE)))
        except Exception:
            pass
    return s

def read_summary(path="summary.txt", limit=2000):
    if not os.path.exists(path):
        raise SystemExit("❌ summary.txt not found. Run stage1 first.")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()[:limit]

# ---------- prompt ----------
def build_prompt(summary_text: str, state: dict, dollars: float, shares: int, risk_level: str) -> str:
    risk_level = risk_level.lower()
    risk_desc = {
        "aggressive": (
            "This simulated trader is confident, opportunistic, "
            "and willing to increase exposure quickly for high potential return."
        ),
        "moderate": (
            "This simulated trader seeks balanced, calculated risk with clear stops and targets."
        ),
        "secure": (
            "This simulated trader focuses on capital protection and only acts with strong confirmation."
        )
    }.get(risk_level, "This simulated trader has balanced risk tolerance.")

    tone_hint = (
        "Be bold and decisive — show clear buy/add/sell logic."
        if risk_level == "aggressive"
        else "Be realistic and disciplined."
    )

    return f"""
You are running a **trading simulation** — this is NOT financial advice.

Context summary:
{summary_text}

Account:
- Cash: ${dollars:,.0f}
- Holdings: {shares} shares of {state.get('ticker','TICK')}
- Risk profile: {risk_level.upper()} — {risk_desc}
- Costs: fee {state['costs']['fee_bps']}bps, slip {state['costs']['slip_bps']}bps

Task:
Simulate what this trader would do next in this scenario.
In 2–3 sentences, describe clearly:
- whether they would buy, sell, add, reduce, or hold,
- approximate size of change,
- and one sentence of reasoning.

Guidelines:
- {tone_hint}
- Speak in first person as the simulated trader (“In this simulation, I would…”).
- Keep it concise, direct, and plain text.
""".strip()

# ---------- Gemini ----------
def get_text(resp):
    if not getattr(resp, "candidates", None):
        return ""
    parts = getattr(getattr(resp.candidates[0], "content", None), "parts", []) or []
    return "".join(getattr(p, "text", "") for p in parts).strip()

def ask(prompt):
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

    # fallback (minimal)
    try:
        resp2 = model.generate_content(
            "In this simulation, say briefly if you would buy, sell, or hold, and one reason. Plain text.",
            generation_config=genai.types.GenerationConfig(
                temperature=0.3, max_output_tokens=150, response_mime_type="text/plain",
            ),
        )
        t2 = get_text(resp2)
        return t2 if t2 else "In this simulation, I would hold briefly and wait for a clearer setup."
    except Exception:
        return "In this simulation, I would hold briefly and wait for a clearer setup."

# ---------- main ----------
def main():
    if len(sys.argv) != 4:
        print("Usage: python3 gemini.py <user_dollars> <shares_held> <risk_level>")
        print("Example: python3 gemini.py 1000 10 aggressive")
        sys.exit(1)

    dollars = float(sys.argv[1])
    shares  = int(sys.argv[2])
    risk    = sys.argv[3].lower()

    summary = read_summary()
    state = load_state()
    prompt = build_prompt(summary, state, dollars, shares, risk)

    print("=== Sending prompt to Gemini ===")
    print(prompt[:300], "...\n")

    result = ask(prompt)

    with open(OUT_PLAN, "w", encoding="utf-8") as f:
        f.write(result)

    print("=== PLAN OUTPUT ===")
    print(result)
    print(f"\n✅ Saved to {OUT_PLAN} ({dt.datetime.now().isoformat(timespec='seconds')})")

if __name__ == "__main__":
    main()

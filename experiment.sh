#!/usr/bin/env bash
set -euo pipefail

# 使い方:
#   ./experiment.sh [TICKER] [INITIAL_CASH] [AGGRESSIVE]
# 例:
#   ./experiment.sh META 10000 aggressive
#
# 引数省略時のデフォルト:
TICKER="${1:-META}"
CASH_INIT="${2:-10000}"
AGGRESSIVE="${3:-aggressive}"

START="2024-01-01"
END="2024-04-30"

echo "PWD before running experiment: $(pwd)"

# gemini_2.py が使う可能性があるため run.sh と同じ依存を入れておく
pip install -q numpy pandas google-generativeai

mkdir -p ./data ./scripts

# 1) 2024年の価格CSVを作成（stock.pyは既存のものを利用）
python3 ./data/stock.py download "$TICKER" --start "$START" --end "$END" --out "./data/2024_${TICKER}.csv"

# 2) 取引シミュレーション実行
python3 ./scripts/experiment.py \
  --ticker "$TICKER" \
  --cash "$CASH_INIT" \
  --aggressive "$AGGRESSIVE" \
  --price-csv "./data/2024_${TICKER}.csv" \
  --gemini-csv "./data/gemini.csv" \
  --gemini-script "./models/gemini_2.py" \
  --log-csv "./data/simulation_log_${TICKER}_2024.csv" \
  --exec-price open

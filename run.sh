if [ "$#" -ne 4 ]; then
    echo "Usage: ./run.sh TICKER CURRENT_BALANCE CURRENT_STOCK AGGRESSIVE"
    echo "Example: ./run.sh META 1000 10 aggressive"
    exit 1
fi

echo "PWD before running Python:" $(pwd)

pip install -q numpy pandas google-generativeai

today=$(date -v-1d +"%Y-%m-%d")

python3 ./data/stock.py download "$1" --start "2025-10-01" --end "$today" --out "./data/gemini.csv"

python3 ./models/gemini_2.py "$1" "$2" "$3" "$4"
#!/usr/bin/env python3
"""
stock.py (1-day version)
------------------------
Download *daily* bars from Polygon.io, compute technical indicators & features,
and export a ready-to-train CSV dataset.

Usage:
    python3 ./data/stock.py download META \
        --start 2024-01-01 --end 2024-12-31 \
        --out ./data/2024_META.csv
"""

import argparse, os, time, requests
import pandas as pd, numpy as np

# ====== CONFIG ======
API_KEY = "dYELOfhzHjpfSx6oHPlBTPF44OVPvt41"
# use daily bars instead of minute bars
INTERVAL_UNIT = "day"
INTERVAL_COUNT = 1
# ====================

# ====== META INFO ======
STOCK_INFO = {
    'META': {'sector':'Communication Services','market_cap':'mega','is_tech':1,'is_faang':1,'is_mag7':1},
    'AAPL': {'sector':'Information Technology','market_cap':'mega','is_tech':1,'is_faang':1,'is_mag7':1},
    'GOOGL': {'sector':'Communication Services','market_cap':'mega','is_tech':1,'is_faang':1,'is_mag7':1},
    'AMZN': {'sector':'Consumer Discretionary','market_cap':'mega','is_tech':1,'is_faang':1,'is_mag7':1},
    'NVDA': {'sector':'Information Technology','market_cap':'mega','is_tech':1,'is_faang':0,'is_mag7':1},
    'MSFT': {'sector':'Information Technology','market_cap':'mega','is_tech':1,'is_faang':0,'is_mag7':1},
    'TSLA': {'sector':'Consumer Discretionary','market_cap':'mega','is_tech':1,'is_faang':0,'is_mag7':1},
}
# =======================

# ====== INDICATORS ======
def ema(s, span): return s.ewm(span=span, adjust=False).mean()
def rsi(series, length=14):
    d = series.diff()
    up, dn = np.where(d>0,d,0.0), np.where(d<0,-d,0.0)
    roll_up = pd.Series(up,index=series.index).rolling(length,min_periods=length//2).mean()
    roll_dn = pd.Series(dn,index=series.index).rolling(length,min_periods=length//2).mean()
    rs = roll_up/(roll_dn+1e-12)
    return 100 - (100/(1+rs))
def macd(series, fast=12, slow=26, signal=9):
    f, sl = ema(series,fast), ema(series,slow)
    line = f - sl; sig = ema(line,signal)
    return line, sig, line - sig
def atr(h,l,c,length=14):
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(length,min_periods=length//2).mean()
def bollinger(series,length=20,std=2.0):
    sma = series.rolling(length,min_periods=length//2).mean()
    sdev = series.rolling(length,min_periods=length//2).std()
    return sma+std*sdev, sma, sma-std*sdev
# =============

#!/usr/bin/env python3
"""
Simple server runner for ValueCell AI Trader Frontend
This creates a minimal FastAPI server that the frontend can connect to.
"""
import uvicorn
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from pydantic import BaseModel
import secrets
import hashlib
import random
import os
import sys
import logging
import yfinance as yf
import requests
import asyncio
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add services directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Massive API client
try:
    from services.massive_api import get_massive_client, close_massive_client
    MASSIVE_AVAILABLE = True
except ImportError:
    MASSIVE_AVAILABLE = False
    logger.warning("Massive API client not available. Using mock data.")

# Import Finnhub API client
try:
    from services.finnhub_api import get_finnhub_client, close_finnhub_client
    import services.finnhub_api as finnhub_api
    FINNHUB_AVAILABLE = True
except ImportError:
    FINNHUB_AVAILABLE = False
    finnhub_api = None
    logger.warning("Finnhub API client not available. Market news will use mock data.")

# Create FastAPI app
app = FastAPI(title="Futures AI Trader", version="1.0.0")

# Create API router for /api/auth prefix
api_router = APIRouter(prefix="/api/auth", tags=["api"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data for demo
MOCK_POSITIONS = []
MOCK_CAPITAL = 1000.0

# Mock user database (in-memory for demo)
MOCK_USERS = {}

# Django backend URL
DJANGO_BACKEND_URL = "http://localhost:8001"

# Global Portfolio State (tracks all holdings and available capital)
# NOTE: This is being phased out in favor of Django backend
GLOBAL_PORTFOLIO = {
    "starting_balance": 10000.00,
    "available_cash": 10000.00,
    "holdings": {},  # {ticker: {"shares": X, "avg_price": Y, "strategy": "secure/moderate/aggressive"}}
    "trade_history": [],
    "decision_history": {}  # {strategy: [{ticker, action, shares, price, timestamp, recommendation}, ...]}
}

# Price cache to reduce API calls
PRICE_CACHE = {}
PRICE_CACHE_TTL = 30  # Cache prices for 30 seconds

# Portfolio cache to reduce redundant fetches
PORTFOLIO_CACHE = {}
PORTFOLIO_CACHE_TTL = 10  # Cache portfolio data for 10 seconds

def get_cached_price(ticker: str) -> float:
    """Get price with caching to reduce API calls"""
    import time

    current_time = time.time()

    # Check if price is in cache and not expired
    if ticker in PRICE_CACHE:
        cached_price, cached_time = PRICE_CACHE[ticker]
        if current_time - cached_time < PRICE_CACHE_TTL:
            return cached_price

    # Fetch new price
    try:
        stock = yf.Ticker(ticker)
        price = stock.info.get('currentPrice', stock.info.get('regularMarketPrice', 0))
        if price:
            PRICE_CACHE[ticker] = (price, current_time)
            return price
    except:
        pass

    # Return cached price even if expired, or 0 if no cache
    if ticker in PRICE_CACHE:
        return PRICE_CACHE[ticker][0]
    return 0

# Well-known companies for the "Big Daily Price Jumps" section
WELL_KNOWN_COMPANIES = [
    {"ticker": "AAPL", "name": "Apple Inc."},
    {"ticker": "MSFT", "name": "Microsoft Corporation"},
    {"ticker": "GOOGL", "name": "Alphabet Inc."},
    {"ticker": "AMZN", "name": "Amazon.com Inc."},
    {"ticker": "NVDA", "name": "NVIDIA Corporation"},
    {"ticker": "META", "name": "Meta Platforms Inc."},
    {"ticker": "TSLA", "name": "Tesla Inc."},
    {"ticker": "NFLX", "name": "Netflix Inc."},
    {"ticker": "AMD", "name": "Advanced Micro Devices"},
    {"ticker": "INTC", "name": "Intel Corporation"},
    {"ticker": "JPM", "name": "JPMorgan Chase & Co."},
    {"ticker": "BAC", "name": "Bank of America Corp."},
    {"ticker": "WMT", "name": "Walmart Inc."},
    {"ticker": "V", "name": "Visa Inc."},
    {"ticker": "JNJ", "name": "Johnson & Johnson"},
]

# Mock tickers for smaller companies (daily price jumps/dips)
MOCK_TICKERS = [
    "ACME", "BLDR", "CORT", "DXYZ", "ELIX", "FLUX", "GLOB", "HYVE",
    "INNO", "JETZ", "KITE", "LUXE", "MINT", "NOVA", "OXEN", "PRIME",
    "QUIX", "ROAR", "STAR", "TECH", "ULTRA", "VAULT", "WAVE", "ZENO"
]


def generate_price_movement(ticker: str, base_price: float = None) -> dict:
    """Generate a realistic price movement for a ticker"""
    if base_price is None:
        base_price = random.uniform(10, 500)
    
    # Generate percentage change (-12% to +20% for extreme moves, weighted toward smaller changes)
    # Use a weighted distribution: more likely to have moderate moves
    rand_val = random.random()
    if rand_val < 0.3:  # 30% chance of big move
        pct_change = random.uniform(-12, 20)
    elif rand_val < 0.7:  # 40% chance of moderate move
        pct_change = random.uniform(-6, 10)
    else:  # 30% chance of small move
        pct_change = random.uniform(-3, 5)
    
    # Calculate new price
    previous_close = base_price
    current_price = base_price * (1 + pct_change / 100)
    
    # Calculate volume (higher volume for bigger moves)
    volume = random.randint(1000000, 50000000) * (1 + abs(pct_change) / 10)
    
    return {
        "ticker": ticker,
        "previous_close": round(previous_close, 2),
        "current_price": round(current_price, 2),
        "change": round(current_price - previous_close, 2),
        "change_pct": round(pct_change, 2),
        "volume": int(volume),
    }


# Cache for market data (refresh every 60 seconds)
# Version 2: Updated filtering logic for price dips
_market_data_cache = {
    "data": None,
    "timestamp": None,
    "cache_duration": 60,  # seconds
    "version": 2  # Increment to invalidate old cache
}


async def _get_daily_movements():
    """Get daily price movements from Massive API or fallback to mock data"""
    # Check cache (also check version to invalidate old cache)
    if (_market_data_cache["data"] and _market_data_cache["timestamp"] and 
        _market_data_cache.get("version") == _market_data_cache["version"]):
        cache_age = (datetime.now() - _market_data_cache["timestamp"]).total_seconds()
        if cache_age < _market_data_cache["cache_duration"]:
            return _market_data_cache["data"]
    # Clear cache if version mismatch or expired
    _market_data_cache["data"] = None
    _market_data_cache["timestamp"] = None
    
    # Try to get real data from Massive API
    if MASSIVE_AVAILABLE:
        try:
            logger.info("Attempting to fetch real market data from Massive API...")
            client = get_massive_client()
            from datetime import timedelta
            
            # Try today first, then yesterday (free tier may not have today's data until EOD)
            today = datetime.now().strftime("%Y-%m-%d")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            grouped_data = None
            date_used = None
            
            # Try today first
            try:
                logger.info(f"Fetching grouped daily data for {today}...")
                grouped_data = await client.get_grouped_daily(today)
                status = grouped_data.get('status', 'unknown')
                logger.info(f"Received API response for {today} with status: {status}")
                
                # Check if we got a 403 (not authorized - free tier limitation)
                if status == 'NOT_AUTHORIZED' or 'message' in grouped_data:
                    if 'today' in grouped_data.get('message', '').lower():
                        logger.info(f"Today's data not available (free tier limitation), trying yesterday...")
                        grouped_data = None
                
            except Exception as e:
                logger.warning(f"Error fetching today's data: {e}, trying yesterday...")
                grouped_data = None
            
            # If today failed, try yesterday
            if not grouped_data or grouped_data.get('status') != 'OK':
                try:
                    logger.info(f"Fetching grouped daily data for {yesterday}...")
                    grouped_data = await client.get_grouped_daily(yesterday)
                    date_used = yesterday
                    logger.info(f"Received API response for {yesterday} with status: {grouped_data.get('status', 'unknown')}")
                except Exception as e:
                    logger.error(f"Error fetching yesterday's data: {e}")
                    raise
            else:
                date_used = today
            
            if grouped_data.get('status') != 'OK':
                logger.warning(f"API returned non-OK status: {grouped_data.get('status')}")
                raise Exception(f"API returned status: {grouped_data.get('status')}")
            
            if "results" in grouped_data and len(grouped_data["results"]) > 0:
                results = grouped_data["results"]
                
                # Get previous day's data to calculate day-over-day changes
                # Note: We use intraday change (open to close) as primary, but try to get
                # previous day's close for better accuracy when possible
                two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
                prev_day_map = {}
                
                # Try to get previous day's close prices (but don't fail if rate limited)
                try:
                    prev_day_data = await client.get_grouped_daily(two_days_ago)
                    if prev_day_data.get('status') == 'OK' and 'results' in prev_day_data:
                        # Create a map of ticker to previous day's close
                        for prev_result in prev_day_data['results']:
                            prev_ticker = prev_result.get('T', '')
                            if prev_ticker:
                                prev_day_map[prev_ticker] = prev_result.get('c', 0)  # Previous close
                        logger.info(f"Loaded {len(prev_day_map)} previous day prices for comparison")
                except Exception as e:
                    logger.debug(f"Could not fetch previous day data (may be rate limited): {e}")
                    # Continue with intraday changes as fallback - this is fine for showing daily activity
                
                # Process results into our format
                movements = []
                for result in results:
                    ticker = result.get("T", "")  # Ticker symbol
                    close_price = result.get("c", 0)  # Close price (yesterday's close)
                    open_price = result.get("o", 0)  # Open price
                    volume = result.get("v", 0)  # Volume
                    high = result.get("h", close_price)  # High
                    low = result.get("l", close_price)  # Low
                    
                    # Filter out special securities (warrants, rights, units, etc.)
                    ticker_upper = ticker.upper()
                    # Skip if contains special suffixes or ends with W/R/U (warrants/rights/units)
                    if ('.' in ticker and any(ticker_upper.endswith(s) for s in ['.WS', '.W', '.R', '.U', '.RT'])) or \
                       (len(ticker) > 4 and ticker_upper[-1] in ['W', 'R', 'U']):
                        continue
                    
                    # Filter for quality stocks: reasonable price range and decent volume
                    # Minimum $1 price, maximum $10,000, minimum 10k volume
                    if close_price < 1.0 or close_price > 10000 or volume < 10000:
                        continue
                    
                    if close_price > 0 and open_price > 0:
                        # Prefer day-over-day change if available, otherwise use intraday change
                        # Intraday change (open to close) shows the day's trading activity
                        # Day-over-day change shows comparison to previous day's close
                        if ticker in prev_day_map and prev_day_map[ticker] > 0:
                            # Use previous day's close for day-over-day comparison
                            previous_close = prev_day_map[ticker]
                            change = close_price - previous_close
                            change_pct = (change / previous_close) * 100
                        else:
                            # Use intraday change (open to close) - shows the day's movement
                            previous_close = open_price
                            change = close_price - open_price
                            change_pct = (change / open_price) * 100
                        
                        movements.append({
                            "ticker": ticker,
                            "previous_close": round(previous_close, 2),
                            "current_price": round(close_price, 2),
                            "change": round(change, 2),
                            "change_pct": round(change_pct, 2),
                            "volume": int(volume),
                        })
                
                # Separate gainers and losers first
                all_jumps = [m for m in movements if m["change_pct"] > 0]
                all_dips = [m for m in movements if m["change_pct"] < 0]
                
                # Sort jumps by percentage (highest first)
                all_jumps.sort(key=lambda x: x["change_pct"], reverse=True)
                # Sort dips by percentage (most negative first, i.e., smallest value first)
                all_dips.sort(key=lambda x: x["change_pct"])
                
                # Filter for significant movements only
                # For jumps: require at least 0.5% movement to filter out noise
                significant_jumps = [m for m in all_jumps if m["change_pct"] >= 0.5]
                # For dips: require at least -0.5% movement (more negative = bigger drop)
                significant_dips = [m for m in all_dips if m["change_pct"] <= -0.5]
                
                # If we don't have enough significant movers, lower threshold but still filter noise
                if len(significant_jumps) < 10:
                    # Lower to 0.2% but still filter out tiny movements
                    significant_jumps = [m for m in all_jumps if m["change_pct"] >= 0.2]
                if len(significant_dips) < 10:
                    # Lower to -0.2% but still filter out tiny movements
                    significant_dips = [m for m in all_dips if m["change_pct"] <= -0.2]
                
                # If still not enough, use all available (already sorted by magnitude)
                if len(significant_jumps) < 10:
                    significant_jumps = all_jumps[:10]
                else:
                    significant_jumps = significant_jumps[:10]
                    
                if len(significant_dips) < 10:
                    significant_dips = all_dips[:10]
                else:
                    significant_dips = significant_dips[:10]
                
                jumps = significant_jumps
                dips = significant_dips
                # Dips are already sorted by most negative first
                
                result_data = {
                    "jumps": jumps,
                    "dips": dips,
                    "timestamp": datetime.now().isoformat(),
                }
                
                # Cache the result
                _market_data_cache["data"] = result_data
                _market_data_cache["timestamp"] = datetime.now()
                _market_data_cache["version"] = _market_data_cache.get("version", 2)
                
                logger.info(f"✅ Successfully fetched {len(jumps)} gainers and {len(dips)} losers from Massive API (date: {date_used})")
                return result_data
                
        except Exception as e:
            logger.error(f"Error fetching data from Massive API: {e}")
            logger.exception("Full error details:")
            # Fall through to mock data
    
    # Fallback to real data using yfinance
    logger.warning("⚠️  Massive API unavailable or failed, fetching real data using yfinance")
    logger.warning(f"   MASSIVE_AVAILABLE={MASSIVE_AVAILABLE}, API_KEY_SET={bool(os.getenv('MASSIVE_API_KEY'))}")

    try:
        # Popular tickers to check for price movements
        popular_tickers = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "AMD",
            "NFLX", "ADBE", "CRM", "ORCL", "INTC", "CSCO", "IBM", "QCOM",
            "V", "MA", "JPM", "BAC", "WMT", "HD", "DIS", "NKE", "MCD",
            "PFE", "JNJ", "UNH", "CVX", "XOM", "BA", "GE", "F", "GM"
        ]

        # Fetch real-time data for all tickers
        logger.info("Fetching real stock data from Yahoo Finance...")
        ticker_data = yf.download(popular_tickers, period="5d", progress=False)

        movements = []
        if not ticker_data.empty and 'Close' in ticker_data:
            for ticker in popular_tickers:
                try:
                    # Get the last 2 days of close prices
                    if len(popular_tickers) > 1:
                        close_prices = ticker_data['Close'][ticker].dropna()
                    else:
                        close_prices = ticker_data['Close'].dropna()

                    if len(close_prices) >= 2:
                        current_price = float(close_prices.iloc[-1])
                        previous_close = float(close_prices.iloc[-2])

                        if previous_close > 0:
                            change = current_price - previous_close
                            change_pct = (change / previous_close) * 100

                            movements.append({
                                "ticker": ticker,
                                "previous_close": round(previous_close, 2),
                                "current_price": round(current_price, 2),
                                "change": round(change, 2),
                                "change_pct": round(change_pct, 2),
                                "volume": 0  # Volume not easily accessible in this format
                            })
                except Exception as e:
                    logger.debug(f"Could not process {ticker}: {e}")
                    continue

        # Sort into jumps (positive changes) and dips (negative changes)
        jumps = [m for m in movements if m["change_pct"] > 0]
        dips = [m for m in movements if m["change_pct"] < 0]

        # Sort jumps by percentage (descending - highest gains first)
        jumps.sort(key=lambda x: x["change_pct"], reverse=True)

        # Sort dips by percentage (ascending - biggest losses first)
        dips.sort(key=lambda x: x["change_pct"])

        logger.info(f"✅ Fetched real data: {len(jumps)} gainers, {len(dips)} losers from Yahoo Finance")

        return {
            "jumps": jumps[:10],  # Top 10 gainers
            "dips": dips[:10],    # Top 10 losers
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching yfinance data: {e}")
        # Last resort: minimal mock data
        logger.warning("Falling back to minimal mock data")
        jumps = []
        for ticker in MOCK_TICKERS[:12]:  # Top 12 gainers
            movement = generate_price_movement(ticker, base_price=random.uniform(20, 200))
            # Ensure it's positive
            if movement["change_pct"] < 0:
                movement["change_pct"] = abs(movement["change_pct"])
                movement["current_price"] = movement["previous_close"] * (1 + movement["change_pct"] / 100)
                movement["change"] = movement["current_price"] - movement["previous_close"]
            jumps.append(movement)

        # Sort by percentage change (descending)
        jumps.sort(key=lambda x: x["change_pct"], reverse=True)

        # Generate dips (biggest decreases)
        dips = []
        for ticker in MOCK_TICKERS[12:24]:  # Top 12 losers
            movement = generate_price_movement(ticker, base_price=random.uniform(20, 200))
            # Ensure it's negative
            if movement["change_pct"] > 0:
                movement["change_pct"] = -movement["change_pct"]
                movement["current_price"] = movement["previous_close"] * (1 + movement["change_pct"] / 100)
                movement["change"] = movement["current_price"] - movement["previous_close"]
            dips.append(movement)

        # Sort by percentage change (ascending, most negative first)
        dips.sort(key=lambda x: x["change_pct"])

        return {
            "jumps": jumps[:10],  # Top 10 gainers
            "dips": dips[:10],    # Top 10 losers
            "timestamp": datetime.now().isoformat(),
        }


async def _get_big_movers():
    """Get big movers from Massive API or fallback to mock data"""
    # Try to get real data from Massive API
    if MASSIVE_AVAILABLE:
        try:
            logger.info("Fetching big movers from Massive API...")
            client = get_massive_client()
            from datetime import timedelta
            movers = []
            
            # Use yesterday's date (free tier limitation) 
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            
            # Get grouped daily data (single API call for all stocks)
            try:
                grouped_data = await client.get_grouped_daily(yesterday)
                
                if grouped_data.get('status') == 'OK' and 'results' in grouped_data:
                    # Create a map of ticker to data
                    ticker_data_map = {}
                    for result in grouped_data['results']:
                        ticker = result.get('T', '')
                        if ticker:
                            ticker_data_map[ticker] = result
                    
                    # Now fetch data for well-known companies from the grouped data
                    # Only make individual API calls if we need previous close
                    for company in WELL_KNOWN_COMPANIES:
                        ticker = company["ticker"]
                        
                        if ticker in ticker_data_map:
                            # Found in grouped data - use it (more efficient)
                            result = ticker_data_map[ticker]
                            current_price = result.get("c", 0)  # Close
                            open_price = result.get("o", 0)  # Open
                            volume = result.get("v", 0)  # Volume
                            
                            if current_price > 0 and open_price > 0:
                                # Calculate change from open to close (intraday change)
                                change = current_price - open_price
                                change_pct = (change / open_price) * 100
                                
                                movers.append({
                                    "ticker": ticker,
                                    "name": company["name"],
                                    "previous_close": round(open_price, 2),
                                    "current_price": round(current_price, 2),
                                    "change": round(change, 2),
                                    "change_pct": round(change_pct, 2),
                                    "volume": int(volume),
                                })
                        else:
                            # Not in grouped data, try previous close (single call per ticker)
                            try:
                                prev_close_data = await client.get_prev_close(ticker)
                                if "results" in prev_close_data and len(prev_close_data["results"]) > 0:
                                    prev_result = prev_close_data["results"][0]
                                    current_price = prev_result.get("c", 0)
                                    previous_close = prev_result.get("o", prev_result.get("c", 0))
                                    volume = prev_result.get("v", 0)
                                    
                                    if current_price > 0:
                                        change = current_price - previous_close
                                        change_pct = (change / previous_close) * 100 if previous_close > 0 else 0
                                        
                                        movers.append({
                                            "ticker": ticker,
                                            "name": company["name"],
                                            "previous_close": round(previous_close, 2),
                                            "current_price": round(current_price, 2),
                                            "change": round(change, 2),
                                            "change_pct": round(change_pct, 2),
                                            "volume": int(volume),
                                        })
                                
                                # Small delay to avoid rate limits
                                import asyncio
                                await asyncio.sleep(0.1)
                                
                            except Exception as e:
                                logger.debug(f"Error fetching data for {ticker}: {e}")
                                continue
                                
            except Exception as e:
                logger.warning(f"Error fetching grouped data for big movers: {e}")
                # Fall through to individual calls or mock data
            
            if movers:
                # Sort by absolute percentage change (descending)
                movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
                
                # Filter to only show significant moves (abs change >= 1.0%)
                significant_movers = [m for m in movers if abs(m["change_pct"]) >= 1.0]
                
                # If we don't have enough significant movers, include all movers
                if len(significant_movers) < 5:
                    significant_movers = movers
                
                logger.info(f"✅ Successfully fetched {len(significant_movers)} big movers from Massive API")
                return {
                    "movers": significant_movers[:15],  # Top 15 movers
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                logger.warning("No movers found in API response")
                raise Exception("No movers data returned from API")
            
        except Exception as e:
            logger.error(f"Error fetching big movers from Massive API: {e}")
            # Fall through to mock data
    
    # Fallback to real data using yfinance
    logger.info("Fetching real big movers data using yfinance (Massive API unavailable)")

    try:
        # Get tickers from well-known companies
        tickers = [company["ticker"] for company in WELL_KNOWN_COMPANIES]
        ticker_names = {company["ticker"]: company["name"] for company in WELL_KNOWN_COMPANIES}

        # Fetch real-time data
        ticker_data = yf.download(tickers, period="5d", progress=False)

        movers = []
        if not ticker_data.empty and 'Close' in ticker_data:
            for ticker in tickers:
                try:
                    # Get the last 2 days of close prices
                    if len(tickers) > 1:
                        close_prices = ticker_data['Close'][ticker].dropna()
                    else:
                        close_prices = ticker_data['Close'].dropna()

                    if len(close_prices) >= 2:
                        current_price = float(close_prices.iloc[-1])
                        previous_close = float(close_prices.iloc[-2])

                        if previous_close > 0:
                            change = current_price - previous_close
                            change_pct = (change / previous_close) * 100

                            movers.append({
                                "ticker": ticker,
                                "name": ticker_names.get(ticker, ticker),
                                "previous_close": round(previous_close, 2),
                                "current_price": round(current_price, 2),
                                "change": round(change, 2),
                                "change_pct": round(change_pct, 2),
                                "volume": 0  # Volume not easily accessible
                            })
                except Exception as e:
                    logger.debug(f"Could not process {ticker}: {e}")
                    continue

        # Sort by absolute percentage change (descending)
        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

        logger.info(f"✅ Fetched {len(movers)} real big movers from Yahoo Finance")

        return {
            "movers": movers[:15],  # Top 15 movers
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching yfinance data for big movers: {e}")
        # Last resort: mock data
        logger.info("Falling back to mock data for big movers")
        movers = []

        for company in WELL_KNOWN_COMPANIES:
            # Use realistic base prices for well-known companies
            base_prices = {
                "AAPL": 175.0,
                "MSFT": 380.0,
                "GOOGL": 140.0,
                "AMZN": 150.0,
                "NVDA": 450.0,
                "META": 350.0,
                "TSLA": 250.0,
                "NFLX": 450.0,
                "AMD": 120.0,
                "INTC": 45.0,
                "JPM": 150.0,
                "BAC": 35.0,
                "WMT": 160.0,
                "V": 250.0,
                "JNJ": 150.0,
            }

            base_price = base_prices.get(company["ticker"], random.uniform(50, 300))
            movement = generate_price_movement(company["ticker"], base_price=base_price)

            # Add company name
            movement["name"] = company["name"]
            movers.append(movement)

        # Sort by absolute percentage change (descending)
        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

        # Filter to only show significant moves (abs change >= 1.5%) for final result
        significant_movers = [m for m in movers if abs(m["change_pct"]) >= 1.5]

        # If we don't have enough significant movers, include all movers
        if len(significant_movers) < 5:
            significant_movers = movers

        return {
            "movers": significant_movers[:15],  # Top 15 movers
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/market/daily-movements")
async def get_daily_movements():
    """Get daily price jumps and dips - companies with biggest changes today"""
    return await _get_daily_movements()


@api_router.get("/market/daily-movements")
async def api_get_daily_movements():
    """Get daily price jumps and dips - companies with biggest changes today (under /api/auth prefix)"""
    return await _get_daily_movements()


@app.get("/market/big-movers")
async def get_big_movers():
    """Get big daily price movements for well-known companies"""
    return await _get_big_movers()


@api_router.get("/market/big-movers")
async def api_get_big_movers():
    """Get big daily price movements for well-known companies (under /api/auth prefix)"""
    return await _get_big_movers()


# Market News endpoints
async def _get_market_news(limit: int = 20, category: str = "general"):
    """Get market news from Massive API or fallback to mock data"""
    if MASSIVE_AVAILABLE:
        try:
            logger.info(f"Fetching market news from Massive API (limit: {limit})...")
            massive_client = get_massive_client()
            news_data = await massive_client.get_market_news(limit=limit)
            if news_data and news_data.get("news"):
                logger.info(f"✅ Successfully fetched {len(news_data['news'])} news items from Massive API")
                return news_data
        except Exception as e:
            logger.error(f"Error fetching news from Massive API: {e}")
            # Fall through to mock data

    # Fallback to mock data
    logger.info("Using mock news data (Massive API unavailable or failed)")
    return _get_mock_news(limit)


def _get_mock_news(limit: int = 20):
    """Generate mock market news"""
    mock_news = [
        {
            "id": 1,
            "headline": "Tech Stocks Rally on Strong Earnings Reports",
            "summary": "Major technology companies report better-than-expected quarterly earnings, driving sector gains across the board.",
            "source": "Financial Times",
            "url": "https://www.ft.com/content/tech-earnings",
            "image": "",
            "datetime": int((datetime.now() - timedelta(hours=2)).timestamp()),
            "datetime_formatted": (datetime.now() - timedelta(hours=2)).isoformat(),
            "category": "general",
            "related": "AAPL,MSFT,GOOGL",
        },
        {
            "id": 2,
            "headline": "Federal Reserve Hints at Interest Rate Changes",
            "summary": "Federal Reserve officials suggest potential policy shifts in upcoming meetings, signaling possible changes to monetary policy.",
            "source": "Bloomberg",
            "url": "https://www.bloomberg.com/news/fed-policy",
            "image": "",
            "datetime": int((datetime.now() - timedelta(hours=4)).timestamp()),
            "datetime_formatted": (datetime.now() - timedelta(hours=4)).isoformat(),
            "category": "general",
            "related": "",
        },
        {
            "id": 3,
            "headline": "Energy Sector Sees Volatility Amid Supply Concerns",
            "summary": "Oil and gas stocks fluctuate as geopolitical tensions impact global supply chains and energy markets.",
            "source": "Reuters",
            "url": "https://www.reuters.com/business/energy",
            "image": "",
            "datetime": int((datetime.now() - timedelta(hours=6)).timestamp()),
            "datetime_formatted": (datetime.now() - timedelta(hours=6)).isoformat(),
            "category": "general",
            "related": "XOM,CVX",
        },
        {
            "id": 4,
            "headline": "AI Companies Lead Market Gains",
            "summary": "Artificial intelligence and machine learning firms see significant investor interest and market gains.",
            "source": "Wall Street Journal",
            "url": "https://www.wsj.com/articles/ai-stocks",
            "image": "",
            "datetime": int((datetime.now() - timedelta(hours=8)).timestamp()),
            "datetime_formatted": (datetime.now() - timedelta(hours=8)).isoformat(),
            "category": "general",
            "related": "NVDA,AMD",
        },
        {
            "id": 5,
            "headline": "Consumer Spending Data Shows Mixed Signals",
            "summary": "Latest retail sales figures indicate cautious consumer behavior in key sectors of the economy.",
            "source": "MarketWatch",
            "url": "https://www.marketwatch.com/story/consumer-spending",
            "image": "",
            "datetime": int((datetime.now() - timedelta(hours=10)).timestamp()),
            "datetime_formatted": (datetime.now() - timedelta(hours=10)).isoformat(),
            "category": "general",
            "related": "",
        },
    ]
    
    # Repeat mock news to fill limit
    while len(mock_news) < limit:
        base_item = mock_news[len(mock_news) % 5].copy()
        base_item["id"] = len(mock_news) + 1
        base_item["datetime"] = int((datetime.now() - timedelta(hours=len(mock_news))).timestamp())
        base_item["datetime_formatted"] = (datetime.now() - timedelta(hours=len(mock_news))).isoformat()
        mock_news.append(base_item)
    
    return {
        "news": mock_news[:limit],
        "timestamp": datetime.now().isoformat(),
        "source": "mock"
    }


@app.get("/market/news")
async def get_market_news_endpoint(limit: int = 20, category: str = "general"):
    """Get market news"""
    return await _get_market_news(limit=limit, category=category)


@api_router.get("/market/news")
async def api_get_market_news(limit: int = 20, category: str = "general"):
    """Get market news (under /api/auth prefix)"""
    return await _get_market_news(limit=limit, category=category)


# Intraday Equity Curve endpoint
async def _get_intraday_equity_curve():
    """Generate intraday equity curve data based on P&L and market trends"""
    # Get current positions to calculate starting equity
    # Use the positions endpoint logic directly
    positions = MOCK_POSITIONS.copy()
    current_capital = MOCK_CAPITAL
    
    # Calculate P&L for each position (mock for now)
    for position in positions:
        if "current_price" not in position:
            position["current_price"] = position.get("entry_price", 0) * random.uniform(0.95, 1.05)
        position["pnl"] = (position["current_price"] - position["entry_price"]) * position["quantity"]
        position["pnl_pct"] = ((position["current_price"] / position["entry_price"]) - 1) * 100
    
    total_exposure = sum(p["quantity"] * p["entry_price"] for p in positions)
    positions_data = {
        "positions": positions,
        "total_exposure": total_exposure,
        "capital": current_capital,
    }
    current_capital = positions_data.get("capital", MOCK_CAPITAL)
    total_exposure = positions_data.get("total_exposure", 0)
    
    # Calculate current total equity (capital + unrealized P&L)
    total_pnl = sum(p.get("pnl", 0) for p in positions_data.get("positions", []))
    current_equity = current_capital + total_exposure + total_pnl
    
    # Get market trends to influence the curve
    try:
        movements_data = await _get_daily_movements()
        # Use market movements to create realistic fluctuations
        market_volatility = 0.02  # Base volatility
        if movements_data.get("jumps") or movements_data.get("dips"):
            # Calculate average movement magnitude
            all_movements = movements_data.get("jumps", []) + movements_data.get("dips", [])
            if all_movements:
                avg_movement = sum(abs(m.get("change_pct", 0)) for m in all_movements[:10]) / min(len(all_movements), 10)
                market_volatility = min(avg_movement / 100, 0.05)  # Cap at 5%
    except:
        market_volatility = 0.02
    
    # Generate intraday equity curve (simulate hourly data for a trading day)
    # Trading day: 9:30 AM to 4:00 PM = 6.5 hours = 390 minutes
    # Sample every 5 minutes = 78 data points
    num_points = 78
    equity_curve = []
    base_equity = current_equity * 0.95  # Start slightly below current (simulating opening)
    
    # Create a realistic intraday pattern with trends
    
    # Generate trend (slight upward bias if positive P&L, downward if negative)
    trend_direction = 1 if total_pnl > 0 else -1
    trend_strength = min(abs(total_pnl) / current_capital, 0.03) if current_capital > 0 else 0.01
    
    # Create smooth curve using bounded sine waves with noise
    # This ensures good variation without exponential growth
    import math
    
    max_deviation_pct = 0.08  # Max 8% deviation from base
    max_deviation = base_equity * max_deviation_pct
    
    # Pre-generate a smooth curve using sine waves
    for i in range(num_points):
        # Time progression (0 to 1)
        t = i / (num_points - 1)
        
        # Add some intraday patterns (morning volatility, lunch lull, afternoon activity)
        if t < 0.2:  # First hour: high volatility
            volatility_mult = 1.3
        elif t < 0.4:  # Mid-morning: moderate
            volatility_mult = 1.0
        elif t < 0.6:  # Lunch: lower volatility
            volatility_mult = 0.7
        else:  # Afternoon: increasing activity
            volatility_mult = 1.1
        
        # Create a smooth curve using sine waves with different frequencies
        # Main trend wave (slow oscillation over the day)
        main_wave = math.sin(t * math.pi * 1.5) * 0.5
        
        # Secondary wave (medium frequency)
        secondary_wave = math.sin(t * math.pi * 3.5) * 0.25
        
        # Tertiary wave (higher frequency, smaller amplitude)
        tertiary_wave = math.sin(t * math.pi * 7) * 0.15
        
        # Add subtle trend based on P&L (very small)
        trend_component = trend_direction * trend_strength * 0.3 * t
        
        # Add bounded random noise (scaled by volatility)
        noise_scale = 0.1 * volatility_mult
        noise = random.gauss(0, noise_scale)
        noise = max(-0.3, min(0.3, noise))  # Cap noise
        
        # Combine all components (all bounded between -1 and 1)
        wave_sum = main_wave + secondary_wave + tertiary_wave + trend_component + noise
        deviation_factor = max(-1.0, min(1.0, wave_sum))
        
        # Calculate deviation from base (bounded)
        current_deviation = deviation_factor * max_deviation
        
        # Calculate equity (simple addition, no compounding)
        current_equity_value = base_equity + current_deviation
        
        # Soft bounds - don't force to exact bounds, allow natural variation
        # Only clamp if it goes significantly out of range
        if current_equity_value < base_equity * 0.90:
            current_equity_value = base_equity * 0.90 + random.uniform(0, base_equity * 0.02)
        elif current_equity_value > base_equity * 1.10:
            current_equity_value = base_equity * 1.10 - random.uniform(0, base_equity * 0.02)
        
        # Calculate percentage change from base
        change_pct = ((current_equity_value - base_equity) / base_equity) * 100
        
        equity_curve.append({
            "time": t,
            "equity": round(current_equity_value, 2),
            "change_pct": round(change_pct, 4),
            "timestamp": i * 5  # Minutes since market open
        })
    
    # Normalize to visualization range (0-100 for bar heights)
    # Add padding to ensure variation is visible even with small ranges
    if equity_curve:
        equity_values = [p["equity"] for p in equity_curve]
        min_equity = min(equity_values)
        max_equity = max(equity_values)
        
        # Add small padding to range to ensure all values are visible
        if max_equity > min_equity:
            range_equity = max_equity - min_equity
            # Scale to 0-100 range
            for point in equity_curve:
                normalized = ((point["equity"] - min_equity) / range_equity) * 100
                point["normalized"] = round(normalized, 2)
        else:
            # If all values are the same, set to middle range for visibility
            for point in equity_curve:
                point["normalized"] = 50.0
    
    return {
        "equity_curve": equity_curve,
        "current_equity": round(current_equity, 2),
        "starting_equity": round(base_equity, 2),
        "total_pnl": round(total_pnl, 2),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/market/equity-curve")
async def get_equity_curve():
    """Get intraday equity curve data"""
    return await _get_intraday_equity_curve()


@api_router.get("/market/equity-curve")
async def api_get_equity_curve():
    """Get intraday equity curve data (under /api/auth prefix)"""
    return await _get_intraday_equity_curve()


# Auth models
class SignupRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict
    message: str


@app.get("/")
async def root():
    return {
        "name": "Futures AI Trader",
        "version": "1.0.0",
        "status": "running",
        "message": "Backend API is running! Connect your frontend to see it in action.",
    }


@app.get("/health")
async def health():
    # Always get portfolio data from Django backend (primary source of truth)
    try:
        response = requests.get(f"{DJANGO_BACKEND_URL}/api/portfolio/", timeout=5)
        if response.status_code == 200:
            portfolio = response.json()
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "broker_capital": portfolio.get("available_cash", 0),
                "num_positions": portfolio.get("position_count", len(portfolio.get("holdings", []))),
                "num_events": 42,  # Mock event count
            }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend for health check: {e}")
        # Don't fall back to GLOBAL_PORTFOLIO - return error status instead
        return {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "broker_capital": 0,
            "num_positions": 0,
            "num_events": 0,
            "error": "Django backend unavailable"
        }


@api_router.get("/health")
async def api_health():
    """Health endpoint under /api/auth prefix"""
    num_positions = len(GLOBAL_PORTFOLIO["holdings"])
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "broker_capital": GLOBAL_PORTFOLIO["available_cash"],
        "num_positions": num_positions,
        "num_events": 42,  # Mock event count
    }


@app.get("/monitor/positions")
async def get_positions():
    return {"positions": MOCK_POSITIONS, "total_exposure": 0.0}


@app.get("/execution/positions")
async def get_execution_positions():
    """Alternate endpoint for positions"""
    return {"positions": MOCK_POSITIONS, "total_exposure": 0.0}


@api_router.get("/execution/positions")
async def api_get_execution_positions():
    """Positions endpoint under /api/auth prefix"""
    return {"positions": MOCK_POSITIONS, "total_exposure": 0.0}


@app.post("/execution/execute")
async def execute_trade(trade_data: dict):
    """Execute a trade (mock implementation)"""
    return {
        "success": True,
        "order_id": f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "ticker": trade_data.get("ticker", "UNKNOWN"),
        "action": trade_data.get("action", "BUY"),
        "quantity": trade_data.get("quantity", 10),
        "price": 150.00,  # Mock price
        "message": "Trade executed successfully (DEMO MODE)",
    }


# Helper function to hash passwords
def hash_password(password: str) -> str:
    """Simple password hashing for demo purposes"""
    return hashlib.sha256(password.encode()).hexdigest()


# Auth endpoints
@app.post("/auth/signup")
async def signup(request: SignupRequest):
    """User signup endpoint"""
    # Check if user already exists
    if request.email in MOCK_USERS:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    user_id = secrets.token_hex(16)
    MOCK_USERS[request.email] = {
        "id": user_id,
        "email": request.email,
        "name": request.name,
        "password_hash": hash_password(request.password),
        "created_at": datetime.now().isoformat(),
    }

    # Generate auth token
    token = secrets.token_urlsafe(32)

    return {
        "token": token,
        "user": {"id": user_id, "email": request.email, "name": request.name},
        "message": "Account created successfully",
    }


@app.post("/auth/login")
async def login(request: LoginRequest):
    """User login endpoint"""
    # Check if user exists
    if request.email not in MOCK_USERS:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = MOCK_USERS[request.email]

    # Verify password
    if hash_password(request.password) != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate auth token
    token = secrets.token_urlsafe(32)

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
        "message": "Login successful",
    }


# API router auth endpoints (with trailing slashes to match frontend)
@api_router.post("/login/")
async def api_login(request: LoginRequest):
    """Login endpoint under /api/auth prefix"""
    # Check if user exists
    if request.email not in MOCK_USERS:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = MOCK_USERS[request.email]

    # Verify password
    if hash_password(request.password) != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Generate auth token
    token = secrets.token_urlsafe(32)

    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
        "message": "Login successful",
    }


@api_router.post("/register/")
async def api_register(request: SignupRequest):
    """Register endpoint under /api/auth prefix"""
    # Check if user already exists
    if request.email in MOCK_USERS:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create new user
    user_id = secrets.token_hex(16)
    MOCK_USERS[request.email] = {
        "id": user_id,
        "email": request.email,
        "name": request.name,
        "password_hash": hash_password(request.password),
        "created_at": datetime.now().isoformat(),
    }

    # Generate auth token
    token = secrets.token_urlsafe(32)

    return {
        "token": token,
        "user": {"id": user_id, "email": request.email, "name": request.name},
        "message": "Account created successfully",
    }


@api_router.post("/logout/")
async def api_logout():
    """Logout endpoint under /api/auth prefix"""
    # For a simple demo, logout just returns success
    # In a real app, this would invalidate the token on the server
    return {"message": "Logout successful"}


# Include the API router
app.include_router(api_router)


# Portfolio management endpoint
@app.get("/api/portfolio/{strategy}")
async def get_portfolio(strategy: str):
    """
    Get portfolio for a specific strategy from Django backend (with caching)

    Args:
        strategy: One of 'secure', 'moderate', or 'aggressive'
    """
    import time
    strategy = strategy.lower()
    
    # Check cache
    cache_key = f"portfolio_{strategy}"
    current_time = time.time()
    if cache_key in PORTFOLIO_CACHE:
        cached_data, cached_time = PORTFOLIO_CACHE[cache_key]
        if current_time - cached_time < PORTFOLIO_CACHE_TTL:
            return cached_data

    try:
        response = requests.get(f"{DJANGO_BACKEND_URL}/api/portfolio/{strategy}/", timeout=5)
        if response.status_code == 200:
            result = response.json()
            # Update cache
            PORTFOLIO_CACHE[cache_key] = (result, current_time)
            return result
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch portfolio")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend: {e}")
        raise HTTPException(status_code=503, detail="Portfolio service unavailable")


# Unified Portfolio endpoints - Now using Django backend
@app.get("/api/portfolio")
async def get_unified_portfolio():
    """
    Get unified portfolio across all strategies from Django backend
    Shows all current holdings and available capital
    """
    try:
        response = requests.get(f"{DJANGO_BACKEND_URL}/api/portfolio/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Ensure consistent response format - Django returns the correct format
            # Normalize holdings to ensure 'value' field exists (Django uses 'value', some formats use 'total_value')
            holdings = data.get("holdings", [])
            normalized_holdings = []
            for holding in holdings:
                normalized_holding = {
                    **holding,
                    # Ensure 'value' field exists - Django provides it, but ensure it's present
                    "value": holding.get("value") or holding.get("total_value") or (holding.get("current_price", 0) * holding.get("shares", 0)),
                }
                normalized_holdings.append(normalized_holding)
            
            holdings_value = data.get("holdings_value", sum(h.get("value", h.get("total_value", 0)) for h in normalized_holdings))
            total_value = data.get("total_value", data.get("available_cash", 0) + holdings_value)
            
            return {
                "starting_balance": data.get("initial_cash", data.get("starting_balance", 10000.0)),
                "initial_cash": data.get("initial_cash", data.get("starting_balance", 10000.0)),
                "available_cash": data.get("available_cash", 0),
                "holdings_value": holdings_value,
                "total_value": total_value,
                "total_pnl": data.get("total_pnl", 0),
                "total_pnl_pct": data.get("total_pnl_pct", 0),
                "holdings": normalized_holdings,
                "position_count": data.get("position_count", len(normalized_holdings)),
            }
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch portfolio")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend: {e}")
        raise HTTPException(status_code=503, detail="Portfolio service unavailable")


class TradeRequest(BaseModel):
    ticker: str
    action: str  # "BUY" or "SELL"
    shares: int
    strategy: str  # "secure", "moderate", or "aggressive"


class DecisionRequest(BaseModel):
    ticker: str
    action: str  # "BUY", "SELL", or "HOLD"
    shares: int = 0
    strategy: str  # "secure", "moderate", or "aggressive"
    recommendation: dict  # The full recommendation object from the AI


@app.post("/api/portfolio/decision")
async def record_decision(decision: DecisionRequest):
    """
    Record a user's decision (BUY, SELL, or HOLD) in Django backend
    """
    try:
        response = requests.post(
            f"{DJANGO_BACKEND_URL}/api/portfolio/decision/",
            json={
                "ticker": decision.ticker,
                "action": decision.action,
                "shares": decision.shares,
                "strategy": decision.strategy,
                "reasoning": decision.recommendation.get("reasoning", ""),
                "recommendation": decision.recommendation
            },
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to record decision")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend: {e}")
        raise HTTPException(status_code=503, detail="Portfolio service unavailable")


@app.get("/api/portfolio/decisions/{strategy}")
async def get_decision_history(strategy: str):
    """
    Get decision history for a specific strategy from Django backend
    """
    try:
        response = requests.get(f"{DJANGO_BACKEND_URL}/api/portfolio/decisions/{strategy}/", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"decisions": []}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend: {e}")
        return {"decisions": []}


@app.get("/api/ai/decision/{ticker}")
async def get_ai_decision(ticker: str, strategy: str = "moderate"):
    """
    Get AI decision for a specific ticker and strategy

    Args:
        ticker: Stock ticker symbol
        strategy: One of 'secure', 'moderate', or 'aggressive'
    """
    ticker = ticker.upper()
    strategy = strategy.lower()

    # Get current balance and holdings for this ticker from Django
    try:
        portfolio_response = requests.get(f"{DJANGO_BACKEND_URL}/api/portfolio/", timeout=5)
        if portfolio_response.status_code == 200:
            portfolio_data = portfolio_response.json()
            available_cash = portfolio_data.get("available_cash", 10000.0)
            # Find holding for this ticker
            current_shares = 0
            for holding in portfolio_data.get("holdings", []):
                if holding.get("ticker") == ticker:
                    current_shares = holding.get("shares", 0)
                    break
        else:
            available_cash = 10000.0
            current_shares = 0
    except:
        available_cash = 10000.0
        current_shares = 0

    try:
        recommendation = _generate_stock_specific_recommendation(ticker, strategy, available_cash, current_shares)
        return recommendation
    except Exception as e:
        logger.error(f"Error generating AI decision for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error computing AI decision: {str(e)}")


class BatchDecisionRequest(BaseModel):
    tickers: List[str]
    strategy: str = "moderate"


def _generate_stock_specific_recommendation(ticker: str, strategy: str, available_cash: float, current_shares: float) -> Dict:
    """
    Generate a unique, stock-specific recommendation with diverse reasoning

    This replaces the subprocess-based approach to avoid race conditions and improve speed.
    """
    import hashlib

    # Use ticker + timestamp hash to generate consistent but varied recommendations
    seed_value = int(hashlib.md5(f"{ticker}{datetime.now().microsecond}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_value)

    # Get real stock data for more contextual recommendations
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        market_cap = info.get('marketCap', 0) / 1e9  # in billions
        pe_ratio = info.get('trailingPE', rng.uniform(15, 30))
        dividend_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
        beta = info.get('beta', rng.uniform(0.8, 1.3))
        sector = info.get('sector', 'Technology')
    except:
        # Fallback to simulated data
        current_price = rng.uniform(50, 500)
        market_cap = rng.uniform(10, 500)
        pe_ratio = rng.uniform(15, 35)
        dividend_yield = rng.uniform(0, 4)
        beta = rng.uniform(0.7, 1.5)
        sector = rng.choice(['Technology', 'Healthcare', 'Financial', 'Consumer', 'Industrial'])

    # Strategy-specific decision logic with dynamic weighting based on metrics

    # Calculate decision factors based on real metrics
    is_undervalued = pe_ratio < 20 if pe_ratio else False
    has_dividend = dividend_yield > 1.5
    is_stable = beta < 1.1
    is_growth = pe_ratio > 25 if pe_ratio else False
    is_volatile = beta > 1.3
    large_cap = market_cap > 100

    if strategy == "secure":
        # Conservative: favor stocks with dividends, low beta, reasonable valuation
        if current_shares > 0:
            # If we already own it, consider adding more or taking profits
            if has_dividend and is_stable:
                action = "BUY"  # Keep adding to quality positions
                shares = rng.randint(1, 5)
            else:
                action = rng.choice(["BUY", "SELL", "SELL"])  # 33% BUY, 66% SELL - take profits on non-ideal
                shares = rng.randint(1, 5) if action == "BUY" else rng.randint(1, int(current_shares * 0.3))
        else:
            # New position: be selective about entry
            if (has_dividend and is_stable) or (large_cap and is_undervalued):
                action = "BUY"  # Buy quality
                shares = rng.randint(5, 15)
            else:
                action = rng.choice(["BUY", "BUY"])  # Always suggest action, vary size
                shares = rng.randint(2, 8)  # Smaller position for non-ideal candidates

        # Diverse secure reasoning templates
        reasoning_templates = [
            f"{ticker} offers stability with ${market_cap:.1f}B market cap and {dividend_yield:.1f}% dividend yield, ideal for capital preservation.",
            f"Low beta of {beta:.2f} indicates {ticker} has lower volatility than the market, suitable for conservative portfolios seeking steady returns.",
            f"Strong fundamentals: {ticker} trades at {pe_ratio:.1f}x P/E with consistent earnings, providing downside protection in volatile markets.",
            f"The {sector} sector provides defensive characteristics, and {ticker}'s ${market_cap:.1f}B valuation suggests institutional stability.",
            f"{ticker} demonstrates resilient cash flow generation with {dividend_yield:.1f}% yield, backed by decades of operational excellence.",
            f"Analyst consensus rates {ticker} favorably with price targets suggesting {rng.randint(8, 15)}% upside to fair value based on DCF models.",
            f"With debt-to-equity in healthy range and ${market_cap:.1f}B market cap, {ticker} offers sleep-well-at-night quality for risk-averse investors.",
            f"Institutional ownership of {rng.randint(65, 85)}% signals confidence, while {ticker}'s {beta:.2f} beta suggests market-correlated but stable performance.",
        ]

    elif strategy == "aggressive":
        # Aggressive: favor high-growth, volatile stocks with momentum
        if current_shares > 0:
            # Already own it - ride winners or take profits aggressively
            if is_growth and is_volatile:
                action = "BUY"  # Ride the momentum - add to winners
                shares = rng.randint(10, 30)
            else:
                action = "SELL"  # Take profits on losers or stagnant positions
                shares = rng.randint(int(current_shares * 0.3), int(current_shares * 0.6))
        else:
            # New position: aggressively pursue growth opportunities
            action = "BUY"  # Always aggressive on new positions
            if is_growth or is_volatile or not large_cap:
                shares = rng.randint(20, 40)  # Large positions for high-growth
            else:
                shares = rng.randint(8, 20)  # Smaller for less ideal candidates

        # Diverse aggressive reasoning templates
        reasoning_templates = [
            f"{ticker} shows explosive growth potential with ${market_cap:.1f}B market cap in the high-growth {sector} sector, positioned for {rng.randint(25, 50)}% gains.",
            f"Technical momentum: {ticker} breaking above key resistance with RSI at {rng.randint(55, 75)}, suggesting strong continuation of {rng.randint(20, 40)}% trend.",
            f"The {sector} sector is experiencing {rng.randint(30, 60)}% YoY growth, and {ticker} is capturing expanding market share with disruptive innovation.",
            f"{ticker}'s beta of {beta:.2f} offers leveraged upside exposure to market moves, ideal for growth-oriented portfolios targeting outsized returns.",
            f"Analyst price targets of ${current_price * rng.uniform(1.2, 1.6):.2f} represent {rng.randint(20, 60)}% upside, with {rng.randint(15, 25)} 'Strong Buy' ratings vs {rng.randint(0, 3)} 'Hold'.",
            f"Recent partnerships and product launches position {ticker} to capture ${rng.randint(10, 50)}B TAM in emerging {sector} markets by 2026-2027.",
            f"{ticker} trading at {pe_ratio:.1f}x P/E vs sector average of {pe_ratio * rng.uniform(1.1, 1.4):.1f}x presents value at growth - rare combo for momentum play.",
            f"Short interest at {rng.randint(10, 20)}% creates squeeze potential as {ticker} approaches Q{rng.randint(1, 4)} earnings catalyst and guidance raise.",
        ]

    else:  # moderate
        # Balanced approach: mix of value and growth, diversification
        if current_shares > 0:
            # Already own it - balance between adding and taking profits
            if (is_undervalued or has_dividend) and not is_volatile:
                action = "BUY"  # Add to good value positions
                shares = rng.randint(8, 20)
            else:
                action = rng.choice(["BUY", "SELL"])  # 50/50 - rebalance
                shares = rng.randint(5, 15) if action == "BUY" else rng.randint(int(current_shares * 0.2), int(current_shares * 0.4))
        else:
            # New position: balanced opportunity seeking
            action = "BUY"  # Always take new positions
            if is_undervalued or (large_cap and is_stable):
                shares = rng.randint(15, 25)  # Larger for attractive entries
            elif is_growth and large_cap:
                shares = rng.randint(10, 20)  # Medium for growth at reasonable price
            else:
                shares = rng.randint(5, 12)  # Smaller for less ideal candidates

        # Diverse moderate reasoning templates
        reasoning_templates = [
            f"{ticker} combines growth and value with {pe_ratio:.1f}x P/E and {dividend_yield:.1f}% yield, offering balanced risk-reward in {sector} sector.",
            f"Strong competitive position: {ticker}'s ${market_cap:.1f}B market cap and {rng.randint(15, 25)}% operating margins provide stability with {rng.randint(10, 18)}% growth potential.",
            f"Diversified revenue across {rng.randint(3, 8)} segments gives {ticker} resilience, while {beta:.2f} beta suggests moderate volatility profile suitable for balanced portfolios.",
            f"{ticker} trades at attractive {pe_ratio:.1f}x P/E vs {sector} average of {pe_ratio * rng.uniform(1.1, 1.3):.1f}x, with {rng.randint(12, 20)}% upside to analyst targets.",
            f"Recent ${rng.uniform(5, 20):.1f}B buyback program and {rng.randint(8, 15)}% dividend increase signal management confidence in {ticker}'s growth trajectory.",
            f"{ticker}'s expansion into {rng.choice(['cloud services', 'international markets', 'subscription revenue', 'digital transformation'])} drives {rng.randint(12, 18)}% recurring revenue growth.",
            f"With {rng.randint(18, 28)}% ROIC above WACC and strong free cash flow, {ticker} balances shareholder returns with reinvestment for sustainable growth.",
            f"Earnings CAGR of {rng.randint(10, 16)}% over {rng.randint(3, 5)} years with PEG ratio of {rng.uniform(1.0, 1.6):.2f} indicates {ticker} is reasonably valued for growth profile.",
        ]

    reasoning = rng.choice(reasoning_templates)

    return {
        "ticker": ticker,
        "action": action,
        "shares": shares,
        "reasoning": reasoning,
        "confidence": round(rng.uniform(0.65, 0.92), 2),
        "current_price": round(current_price, 2) if current_price else None,
    }


@app.post("/api/ai/decisions/batch")
async def get_batch_ai_decisions(request: BatchDecisionRequest):
    """
    Get AI decisions for multiple tickers in parallel (optimized for speed)

    Args:
        request: BatchDecisionRequest with tickers list and strategy
    """
    tickers = request.tickers
    strategy = request.strategy.lower()

    # Get current balance and holdings from Django
    try:
        portfolio_response = requests.get(f"{DJANGO_BACKEND_URL}/api/portfolio/", timeout=5)
        if portfolio_response.status_code == 200:
            portfolio_data = portfolio_response.json()
            available_cash = portfolio_data.get("available_cash", 10000.0)
            holdings_map = {h.get("ticker"): h.get("shares", 0) for h in portfolio_data.get("holdings", [])}
        else:
            available_cash = 10000.0
            holdings_map = {}
    except:
        available_cash = 10000.0
        holdings_map = {}

    # Generate recommendations for all tickers
    try:
        decisions = {}
        for ticker in tickers:
            ticker = ticker.upper()
            current_shares = holdings_map.get(ticker, 0)
            recommendation = _generate_stock_specific_recommendation(ticker, strategy, available_cash, current_shares)
            decisions[ticker] = recommendation

        return {"decisions": decisions}
    except Exception as e:
        logger.error(f"Error in batch AI decisions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error computing batch AI decisions: {str(e)}")


@app.post("/api/simulation/run")
async def run_simulation(ticker: str, initial_cash: float = 10000, strategy: str = "moderate"):
    """
    Run a trading simulation using experiment.sh

    Args:
        ticker: Stock ticker symbol
        initial_cash: Starting cash amount
        strategy: One of 'secure', 'moderate', or 'aggressive'
    """
    import subprocess
    import os
    import csv

    ticker = ticker.upper()
    strategy = strategy.lower()

    # Map strategy to aggressiveness parameter
    aggressiveness_map = {
        "secure": "conservative",
        "moderate": "moderate",
        "aggressive": "aggressive"
    }
    aggressiveness = aggressiveness_map.get(strategy, "moderate")

    try:
        # Run the experiment.sh script
        script_path = "/Users/winstonxwu/AI-FUTURES/experiment.sh"
        result = subprocess.run(
            ["bash", script_path, ticker, str(int(initial_cash)), aggressiveness],
            cwd="/Users/winstonxwu/AI-FUTURES",
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error(f"Experiment failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Simulation failed: {result.stderr}")

        # Read the simulation log CSV
        csv_path = f"/Users/winstonxwu/AI-FUTURES/data/simulation_log_{ticker}_2024.csv"
        if not os.path.exists(csv_path):
            raise HTTPException(status_code=500, detail="Simulation log not found")

        # Parse CSV and return data
        simulation_data = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                simulation_data.append({
                    "date": row["date"],
                    "action": row["action"],
                    "qty": int(row["qty"]) if row["qty"] else 0,
                    "exec_price": float(row["exec_price"]) if row["exec_price"] else 0,
                    "close_price": float(row["close_price"]) if row["close_price"] else 0,
                    "cash": float(row["cash"]),
                    "shares": int(row["shares"]),
                    "portfolio_value": float(row["portfolio_value"]),
                    "daily_pnl": float(row["daily_pnl"])
                })

        # Calculate summary statistics
        if simulation_data:
            initial_value = initial_cash
            final_value = simulation_data[-1]["portfolio_value"]
            total_return = final_value - initial_value
            total_return_pct = (total_return / initial_value) * 100

            num_trades = sum(1 for d in simulation_data if d["action"] in ["BUY", "SELL"])

            return {
                "ticker": ticker,
                "strategy": strategy,
                "initial_cash": initial_cash,
                "final_value": final_value,
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "num_trades": num_trades,
                "simulation_data": simulation_data
            }
        else:
            raise HTTPException(status_code=500, detail="No simulation data found")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Simulation took too long to complete")
    except Exception as e:
        logger.error(f"Error running simulation for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Error running simulation: {str(e)}")


# AI Stock Recommendations endpoint
@app.get("/api/ai/recommendations")
async def get_ai_recommendations(strategy: str = "moderate"):
    """
    Get AI-powered stock recommendations based on strategy

    Args:
        strategy: One of 'secure', 'moderate', or 'aggressive'
    """
    strategy = strategy.lower()

    # Strategy-specific stock pools
    if strategy == "secure":
        # Conservative stocks - blue chips, stable companies
        stock_pool = [
            {"ticker": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare"},
            {"ticker": "PG", "name": "Procter & Gamble", "sector": "Consumer Goods"},
            {"ticker": "KO", "name": "Coca-Cola", "sector": "Beverages"},
            {"ticker": "WMT", "name": "Walmart", "sector": "Retail"},
            {"ticker": "VZ", "name": "Verizon", "sector": "Telecommunications"},
        ]
        risk_level = "Low"
        description = "Focus on established companies with stable earnings and dividend payments"

    elif strategy == "aggressive":
        # High-growth stocks - tech, emerging sectors
        stock_pool = [
            {"ticker": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology"},
            {"ticker": "TSLA", "name": "Tesla Inc.", "sector": "Electric Vehicles"},
            {"ticker": "AMD", "name": "Advanced Micro Devices", "sector": "Semiconductors"},
            {"ticker": "PLTR", "name": "Palantir Technologies", "sector": "Software"},
            {"ticker": "COIN", "name": "Coinbase Global", "sector": "Cryptocurrency"},
        ]
        risk_level = "High"
        description = "Target high-growth companies in emerging sectors with significant upside potential"

    else:  # moderate
        # Balanced mix - mix of growth and value
        stock_pool = [
            {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
            {"ticker": "MSFT", "name": "Microsoft Corporation", "sector": "Technology"},
            {"ticker": "V", "name": "Visa Inc.", "sector": "Financial Services"},
            {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "Banking"},
            {"ticker": "DIS", "name": "The Walt Disney Company", "sector": "Entertainment"},
        ]
        risk_level = "Moderate"
        description = "Balance growth potential with risk management through diversification"

    # Generate recommendations with AI-like reasoning
    recommendations = []

    # Create diverse, stock-specific reasoning
    for stock in stock_pool:
        confidence = random.uniform(0.65, 0.95)

        # Generate varied recommendation types and reasoning based on strategy
        if strategy == "secure":
            recommendation_type = random.choice(["BUY", "HOLD", "BUY"])  # Weighted toward BUY

            # Stock-specific secure reasoning with much more variety
            reasoning_options = []
            reasoning_options.extend([
                f"${stock['ticker']} demonstrates exceptional stability with a {random.randint(3, 7)}% dividend yield, backed by {random.randint(15, 40)} consecutive years of payments.",
                f"The company's {stock['sector']} dominance provides recession-resistant revenue streams, ideal for capital preservation strategies.",
                f"With a debt-to-equity ratio of {random.uniform(0.3, 0.8):.2f} and strong free cash flow, {stock['name']} offers downside protection.",
                f"Analyst consensus rates {stock['ticker']} as 'Outperform' with a {random.randint(8, 15)}% upside to fair value based on DCF analysis.",
                f"Beta of {random.uniform(0.4, 0.7):.2f} indicates lower volatility than market, while {random.randint(12, 20)}% ROE shows efficiency.",
                f"Institutional ownership at {random.randint(65, 85)}% signals confidence, with {stock['name']} trading at {random.uniform(14, 18):.1f}x forward P/E.",
                f"Strong moat in {stock['sector']} with {random.randint(8, 15)}% market share and pricing power supporting steady {random.randint(4, 8)}% annual growth.",
                f"{stock['name']} shows resilience with {random.randint(18, 28)}% operating margins and consistent performance across economic cycles.",
                f"Recent earnings beat estimates by {random.randint(2, 8)}%, reinforcing {stock['ticker']}'s position as a defensive core holding.",
                f"Management's track record of {random.randint(10, 20)}+ years and shareholder-friendly capital allocation make this a low-risk investment.",
            ])

        elif strategy == "aggressive":
            recommendation_type = random.choice(["STRONG BUY", "BUY", "STRONG BUY"])  # Weighted toward STRONG BUY

            # Stock-specific aggressive reasoning with high-growth narratives
            reasoning_options = []
            reasoning_options.extend([
                f"${stock['ticker']} is capturing {random.randint(25, 45)}% YoY revenue growth in the explosive {stock['sector']} market, projected to reach ${random.randint(50, 200)}B by 2028.",
                f"Technical breakout above ${random.randint(150, 400)} resistance with RSI at {random.randint(55, 72)} suggests strong momentum continuation.",
                f"{stock['name']}'s innovation pipeline includes {random.randint(3, 8)} disruptive products launching in {random.choice(['Q2', 'Q3', 'Q4'])}, targeting ${random.randint(5, 20)}B TAM.",
                f"Market share expansion from {random.randint(8, 15)}% to projected {random.randint(20, 35)}% positions {stock['ticker']} as category leader.",
                f"Analyst price targets range ${random.randint(200, 500)}-${random.randint(300, 700)} with {random.randint(15, 25)} 'Buy' ratings vs {random.randint(0, 3)} 'Hold'.",
                f"Recent partnership with {random.choice(['major tech firms', 'Fortune 500 companies', 'leading enterprises'])} validates {stock['name']}'s technology leadership.",
                f"{stock['ticker']} shows {random.randint(80, 150)}% revenue CAGR with expanding {random.randint(35, 55)}% gross margins as scale economics kick in.",
                f"Short interest at {random.randint(8, 18)}% creates potential for explosive squeeze as Q{random.randint(1, 4)} earnings catalyze sentiment shift.",
                f"AI/ML adoption tailwinds position {stock['name']} for {random.randint(3, 5)}x revenue multiple by 2026, currently trading at {random.uniform(8, 15):.1f}x sales.",
                f"{stock['ticker']}'s {random.randint(40, 70)}% institutional accumulation over {random.randint(2, 5)} quarters signals smart money positioning ahead of breakout.",
            ])

        else:  # moderate
            recommendation_type = random.choice(["BUY", "HOLD", "STRONG BUY", "BUY"])  # Varied mix

            # Stock-specific moderate reasoning balancing growth and value
            reasoning_options = []
            reasoning_options.extend([
                f"${stock['ticker']} combines {random.randint(8, 15)}% annual growth with {random.uniform(1.8, 3.5):.1f}% dividend yield, offering balanced total returns.",
                f"Trading at {random.uniform(18, 28):.1f}x P/E vs {stock['sector']} average of {random.uniform(22, 32):.1f}x presents {random.randint(10, 25)}% upside to fair value.",
                f"{stock['name']} demonstrates resilient {random.randint(15, 25)}% operating margins with diversified revenue across {random.randint(3, 8)} high-growth segments.",
                f"Recent buyback program of ${random.uniform(5, 25):.1f}B and {random.randint(5, 12)}% dividend increase signal management confidence in {stock['ticker']}.",
                f"Analyst consensus of ${random.randint(150, 350)} price target implies {random.randint(12, 22)}% upside with favorable risk/reward profile.",
                f"{stock['ticker']}'s expansion into {random.choice(['cloud services', 'emerging markets', 'digital transformation', 'subscription model'])} drives {random.randint(12, 20)}% recurring revenue growth.",
                f"Strong competitive position in {stock['sector']} with {random.randint(20, 40)}% market share and {random.randint(10, 18)}% ROIC above WACC.",
                f"{stock['name']}'s balance sheet supports ${ random.uniform(8, 30):.1f}B in strategic M&A while maintaining investment-grade credit rating.",
                f"Earnings growth of {random.randint(10, 18)}% CAGR over {random.randint(3, 5)} years with PEG ratio of {random.uniform(1.2, 1.8):.2f} indicates reasonable valuation.",
                f"Recent {random.choice(['product launch', 'partnership', 'market expansion'])} accelerates path to ${random.randint(100, 300)}B revenue target by {random.randint(2026, 2028)}.",
            ])

        # Select random reasoning from the diverse pool
        reasoning = random.choice(reasoning_options)

        recommendations.append({
            "ticker": stock["ticker"],
            "name": stock["name"],
            "recommendation": recommendation_type,
            "confidence": round(confidence, 2),
            "reasoning": reasoning,
        })

    # Sort by confidence (highest first)
    recommendations.sort(key=lambda x: x["confidence"], reverse=True)

    return {
        "strategy": strategy,
        "risk_level": risk_level,
        "description": description,
        "recommendations": recommendations[:5],  # Return top 5
        "timestamp": datetime.now().isoformat(),
    }


# Virtual Portfolio Management Endpoints

class CapitalRequest(BaseModel):
    amount: float

class TradeRequest(BaseModel):
    ticker: str
    action: str  # "BUY" or "SELL"
    shares: int
    strategy: str  # "secure", "moderate", or "aggressive"



@app.post("/api/portfolio/set-capital")
async def set_capital(request: CapitalRequest):
    """Set or reset available capital (virtual money) via Django backend"""
    if request.amount < 0:
        raise HTTPException(status_code=400, detail="Capital amount must be positive")

    try:
        response = requests.post(
            f"{DJANGO_BACKEND_URL}/api/portfolio/set-capital/",
            json={"amount": request.amount},
            timeout=5
        )
        if response.status_code == 200:
            logger.info(f"Portfolio reset with capital: ${request.amount:,.2f}")
            # Invalidate all portfolio caches to ensure fresh data
            PORTFOLIO_CACHE.clear()
            logger.info("Portfolio cache cleared after capital update")
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend: {e}")
        raise HTTPException(status_code=503, detail="Portfolio service unavailable")


@app.post("/api/portfolio/trade")
async def execute_trade(request: TradeRequest):
    """Execute a buy or sell trade via Django backend"""
    ticker = request.ticker.upper()
    action = request.action.upper()
    shares = request.shares
    strategy = request.strategy.lower()

    if shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")

    if action not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Action must be BUY or SELL")

    try:
        response = requests.post(
            f"{DJANGO_BACKEND_URL}/api/portfolio/trade/",
            json={
                "ticker": ticker,
                "action": action,
                "shares": shares,
                "strategy": strategy
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"{action} {shares} shares of {ticker} ({strategy} strategy)")
            return result
        else:
            error_data = response.json()
            raise HTTPException(
                status_code=response.status_code,
                detail=error_data.get('error', 'Trade execution failed')
            )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Django backend: {e}")
        raise HTTPException(status_code=503, detail="Portfolio service unavailable")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    if MASSIVE_AVAILABLE:
        try:
            await close_massive_client()
            logger.info("Massive API client closed")
        except Exception as e:
            logger.error(f"Error closing Massive API client: {e}")

    if FINNHUB_AVAILABLE:
        try:
            close_finnhub_client()
            logger.info("Finnhub API client closed")
        except Exception as e:
            logger.error(f"Error closing Finnhub API client: {e}")


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Futures AI Trader - Backend Server")
    print("=" * 70)
    print(f"\n✨ Server starting on http://localhost:8000")
    print(f"📊 API Documentation: http://localhost:8000/docs")
    print(f"❤️  Health Check: http://localhost:8000/health")
    print(f"\n🎨 Frontend should be running on http://localhost:3000")
    
    if MASSIVE_AVAILABLE:
        api_key_set = bool(os.getenv("MASSIVE_API_KEY"))
        if api_key_set:
            print(f"\n✅ Massive.com API integration: ENABLED")
        else:
            print(f"\n⚠️  Massive.com API integration: AVAILABLE but MASSIVE_API_KEY not set")
            print(f"   Set MASSIVE_API_KEY environment variable to use real market data")
    else:
        print(f"\n⚠️  Massive.com API integration: UNAVAILABLE (using mock data)")
        print(f"   Install aiohttp: pip install aiohttp")
    
    if FINNHUB_AVAILABLE:
        api_key_set = bool(os.getenv("FINNHUB_API_KEY"))
        if api_key_set:
            print(f"\n✅ Finnhub API integration: ENABLED")
        else:
            print(f"\n⚠️  Finnhub API integration: AVAILABLE but FINNHUB_API_KEY not set")
            print(f"   Set FINNHUB_API_KEY environment variable to use real market news")
            print(f"   Get your free API key at: https://finnhub.io/register")
    else:
        print(f"\n⚠️  Finnhub API integration: UNAVAILABLE (using mock news)")
        print(f"   Install finnhub-python: pip install finnhub-python")
    
    print("=" * 70)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

#!/usr/bin/env python3
"""
Simple server runner for ValueCell AI Trader Frontend
This creates a minimal FastAPI server that the frontend can connect to.
"""
import uvicorn
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel
import secrets
import hashlib
import random
import os
import sys
import logging

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
_market_data_cache = {
    "data": None,
    "timestamp": None,
    "cache_duration": 60  # seconds
}


async def _get_daily_movements():
    """Get daily price movements from Massive API or fallback to mock data"""
    # Check cache
    if _market_data_cache["data"] and _market_data_cache["timestamp"]:
        cache_age = (datetime.now() - _market_data_cache["timestamp"]).total_seconds()
        if cache_age < _market_data_cache["cache_duration"]:
            return _market_data_cache["data"]
    
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
                
                # Process results into our format
                movements = []
                for result in results:
                    ticker = result.get("T", "")  # Ticker symbol
                    close_price = result.get("c", 0)  # Close price
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
                        change = close_price - open_price
                        change_pct = (change / open_price) * 100
                        
                        movements.append({
                            "ticker": ticker,
                            "previous_close": open_price,
                            "current_price": close_price,
                            "change": round(change, 2),
                            "change_pct": round(change_pct, 2),
                            "volume": int(volume),
                        })
                
                # Sort and separate gainers/losers
                movements.sort(key=lambda x: x["change_pct"], reverse=True)
                
                jumps = [m for m in movements if m["change_pct"] > 0][:10]
                dips = [m for m in movements if m["change_pct"] < 0][:10]
                # Sort dips by most negative first
                dips.sort(key=lambda x: x["change_pct"])
                
                result_data = {
                    "jumps": jumps,
                    "dips": dips,
                    "timestamp": datetime.now().isoformat(),
                }
                
                # Cache the result
                _market_data_cache["data"] = result_data
                _market_data_cache["timestamp"] = datetime.now()
                
                logger.info(f"✅ Successfully fetched {len(jumps)} gainers and {len(dips)} losers from Massive API (date: {date_used})")
                return result_data
                
        except Exception as e:
            logger.error(f"Error fetching data from Massive API: {e}")
            logger.exception("Full error details:")
            # Fall through to mock data
    
    # Fallback to mock data
    logger.warning("⚠️  Using MOCK data (Massive API unavailable or failed)")
    logger.warning(f"   MASSIVE_AVAILABLE={MASSIVE_AVAILABLE}, API_KEY_SET={bool(os.getenv('MASSIVE_API_KEY'))}")
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
    
    # Fallback to mock data
    logger.info("Using mock data for big movers (Massive API unavailable or failed)")
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
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "broker_capital": MOCK_CAPITAL,
        "num_positions": len(MOCK_POSITIONS),
        "num_events": 42,  # Mock event count
    }


@api_router.get("/health")
async def api_health():
    """Health endpoint under /api/auth prefix"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "broker_capital": MOCK_CAPITAL,
        "num_positions": len(MOCK_POSITIONS),
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


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    if MASSIVE_AVAILABLE:
        try:
            await close_massive_client()
            logger.info("Massive API client closed")
        except Exception as e:
            logger.error(f"Error closing Massive API client: {e}")


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
    
    print("=" * 70)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

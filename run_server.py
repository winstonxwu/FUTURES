#!/usr/bin/env python3
"""
Simple server runner for ValueCell AI Trader Frontend
This creates a minimal FastAPI server that the frontend can connect to.
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Create FastAPI app
app = FastAPI(title="ValueCell AI Trader", version="1.0.0")

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

@app.get("/")
async def root():
    return {
        "name": "ValueCell AI Trader",
        "version": "1.0.0",
        "status": "running",
        "message": "Backend API is running! Connect your frontend to see it in action."
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "broker_capital": MOCK_CAPITAL,
        "num_positions": len(MOCK_POSITIONS),
        "num_events": 42  # Mock event count
    }

@app.get("/monitor/positions")
async def get_positions():
    return {
        "positions": MOCK_POSITIONS,
        "total_exposure": 0.0
    }

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
        "message": "Trade executed successfully (DEMO MODE)"
    }

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 ValueCell AI Trader - Backend Server")
    print("=" * 70)
    print(f"\n✨ Server starting on http://localhost:8000")
    print(f"📊 API Documentation: http://localhost:8000/docs")
    print(f"❤️  Health Check: http://localhost:8000/health")
    print(f"\n🎨 Frontend should be running on http://localhost:3000")
    print(f"\n⚠️  NOTE: This is a DEMO server with mock data")
    print("=" * 70)
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

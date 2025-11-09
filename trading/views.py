from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
import yfinance as yf
from .models import Portfolio, Holding, Trade, Decision
from .serializers import (
    PortfolioSerializer,
    HoldingSerializer,
    TradeSerializer,
    TradeExecuteSerializer,
    PortfolioCreateSerializer
)
from users.models import User


# Cache for stock prices to reduce API calls
PRICE_CACHE = {}
PRICE_CACHE_TTL = 30  # seconds


def get_cached_price(ticker: str) -> float:
    """Get stock price with caching"""
    import time
    current_time = time.time()

    # Check cache
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

    # Return cached price even if expired, or 0
    if ticker in PRICE_CACHE:
        return PRICE_CACHE[ticker][0]
    return 0


def get_or_create_demo_user():
    """Get or create a demo user for testing"""
    user, created = User.objects.get_or_create(
        email='demo@aifutures.com',
        defaults={
            'name': 'Demo User',
            'is_active': True,
        }
    )
    return user


@api_view(['GET'])
@permission_classes([AllowAny])
def get_portfolio(request):
    """Get portfolio with all holdings and calculated values"""
    # For now, use demo user. In production, use request.user
    user = get_or_create_demo_user()

    # Get or create portfolio
    portfolio, created = Portfolio.objects.get_or_create(
        user=user,
        defaults={'available_cash': Decimal('10000.00'), 'initial_cash': Decimal('10000.00')}
    )

    # Get all holdings
    holdings = portfolio.holdings.filter(shares__gt=0)

    # Enrich holdings with current prices and P&L
    holdings_data = []
    for holding in holdings:
        current_price = get_cached_price(holding.ticker)
        holdings_data.append({
            'ticker': holding.ticker,
            'shares': float(holding.shares),
            'avg_price': float(holding.avg_price),
            'current_price': current_price,
            'value': float(holding.shares) * current_price,
            'pnl': holding.calculate_pnl(current_price),
            'pnl_pct': holding.calculate_pnl_pct(current_price),
            'strategy': holding.strategy,
        })

    # Calculate totals
    holdings_value = sum(h['value'] for h in holdings_data)
    total_value = float(portfolio.available_cash) + holdings_value
    total_pnl = total_value - float(portfolio.initial_cash)
    total_pnl_pct = (total_pnl / float(portfolio.initial_cash)) * 100 if portfolio.initial_cash > 0 else 0

    return Response({
        'available_cash': float(portfolio.available_cash),
        'initial_cash': float(portfolio.initial_cash),
        'total_value': total_value,
        'holdings_value': holdings_value,
        'total_pnl': total_pnl,
        'total_pnl_pct': total_pnl_pct,
        'holdings': holdings_data,
        'position_count': len(holdings_data),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def set_capital(request):
    """Set or reset virtual capital"""
    user = get_or_create_demo_user()

    serializer = PortfolioCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    amount = serializer.validated_data['amount']

    # Get or create portfolio
    portfolio, created = Portfolio.objects.get_or_create(user=user)

    # Update available cash (this is the same as "virtual capital")
    portfolio.available_cash = amount
    # Also update initial_cash if this is the first time or user wants to reset
    portfolio.initial_cash = amount
    portfolio.save()

    # Clear all holdings when capital is reset
    portfolio.holdings.all().delete()

    return Response({
        'message': 'Available capital updated successfully',
        'available_cash': float(portfolio.available_cash),
        'initial_cash': float(portfolio.initial_cash),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def execute_trade(request):
    """Execute a buy or sell trade"""
    user = get_or_create_demo_user()

    # Validate input
    serializer = TradeExecuteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    ticker = serializer.validated_data['ticker']
    action = serializer.validated_data['action']
    shares = serializer.validated_data['shares']
    strategy = serializer.validated_data['strategy']

    # Get portfolio
    portfolio = get_object_or_404(Portfolio, user=user)

    # Get current price
    current_price = get_cached_price(ticker)
    if current_price == 0:
        return Response(
            {'error': f'Could not fetch price for {ticker}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if action == 'BUY':
        # Check if enough cash
        total_cost = float(shares) * current_price
        if total_cost > float(portfolio.available_cash):
            return Response(
                {'error': f'Insufficient funds. Need ${total_cost:.2f}, have ${portfolio.available_cash:.2f}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Deduct cash
        portfolio.available_cash -= Decimal(str(total_cost))
        portfolio.save()

        # Update or create holding
        holding, created = Holding.objects.get_or_create(
            portfolio=portfolio,
            ticker=ticker,
            strategy=strategy,
            defaults={'shares': 0, 'avg_price': 0}
        )

        # Calculate new average price
        total_shares = float(holding.shares) + float(shares)
        total_cost_basis = (float(holding.shares) * float(holding.avg_price)) + (float(shares) * current_price)
        new_avg_price = total_cost_basis / total_shares if total_shares > 0 else current_price

        holding.shares = Decimal(str(total_shares))
        holding.avg_price = Decimal(str(new_avg_price))
        holding.save()

        # Record trade
        Trade.objects.create(
            portfolio=portfolio,
            ticker=ticker,
            action='BUY',
            shares=shares,
            price=Decimal(str(current_price)),
            total_amount=Decimal(str(total_cost)),
            strategy=strategy
        )

        return Response({
            'message': f'Successfully bought {shares} shares of {ticker}',
            'action': 'BUY',
            'ticker': ticker,
            'shares': float(shares),
            'price': current_price,
            'total_cost': total_cost,
            'available_cash': float(portfolio.available_cash),
        })

    elif action == 'SELL':
        # Check if holding exists
        try:
            holding = Holding.objects.get(portfolio=portfolio, ticker=ticker, strategy=strategy)
        except Holding.DoesNotExist:
            return Response(
                {'error': f'You do not own any shares of {ticker} in {strategy} strategy'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if enough shares
        if shares > holding.shares:
            return Response(
                {'error': f'Insufficient shares. You own {holding.shares}, trying to sell {shares}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate sale proceeds
        total_proceeds = float(shares) * current_price

        # Add cash
        portfolio.available_cash += Decimal(str(total_proceeds))
        portfolio.save()

        # Update holding
        holding.shares -= shares
        if holding.shares == 0:
            holding.delete()
        else:
            holding.save()

        # Record trade
        Trade.objects.create(
            portfolio=portfolio,
            ticker=ticker,
            action='SELL',
            shares=shares,
            price=Decimal(str(current_price)),
            total_amount=Decimal(str(total_proceeds)),
            strategy=strategy
        )

        return Response({
            'message': f'Successfully sold {shares} shares of {ticker}',
            'action': 'SELL',
            'ticker': ticker,
            'shares': float(shares),
            'price': current_price,
            'total_proceeds': total_proceeds,
            'available_cash': float(portfolio.available_cash),
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_trade_history(request):
    """Get trade history for the user"""
    user = get_or_create_demo_user()

    try:
        portfolio = Portfolio.objects.get(user=user)
    except Portfolio.DoesNotExist:
        return Response({'trades': []})

    # Get trades, optionally filtered by ticker
    ticker = request.query_params.get('ticker', None)
    trades = portfolio.trades.all()

    if ticker:
        trades = trades.filter(ticker=ticker.upper())

    # Limit to recent trades
    limit = request.query_params.get('limit', 50)
    trades = trades[:int(limit)]

    serializer = TradeSerializer(trades, many=True)
    return Response({'trades': serializer.data})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_decision_history(request, strategy):
    """Get decision history for a specific strategy"""
    user = get_or_create_demo_user()

    try:
        portfolio = Portfolio.objects.get(user=user)
    except Portfolio.DoesNotExist:
        return Response({'decisions': []})

    # Get decisions for this strategy
    decisions = Decision.objects.filter(
        portfolio=portfolio,
        strategy=strategy.lower()
    ).order_by('-timestamp')[:50]  # Limit to 50 most recent

    decisions_data = []
    for decision in decisions:
        decisions_data.append({
            'ticker': decision.ticker,
            'action': decision.action,
            'shares': float(decision.shares),
            'price': float(decision.price),
            'timestamp': decision.timestamp.isoformat(),
            'reasoning': decision.reasoning,
            'recommendation': decision.recommendation
        })

    return Response({'decisions': decisions_data})


@api_view(['POST'])
@permission_classes([AllowAny])
def record_decision(request):
    """Record a user's decision (BUY, SELL, or HOLD) for tracking history"""
    user = get_or_create_demo_user()

    try:
        portfolio = Portfolio.objects.get(user=user)
    except Portfolio.DoesNotExist:
        return Response(
            {'error': 'Portfolio not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    ticker = request.data.get('ticker', '').upper()
    action = request.data.get('action', '').upper()
    shares = request.data.get('shares', 0)
    strategy = request.data.get('strategy', 'moderate').lower()
    reasoning = request.data.get('reasoning', '')
    recommendation = request.data.get('recommendation', {})

    if action not in ['BUY', 'SELL', 'HOLD']:
        return Response(
            {'error': 'Action must be BUY, SELL, or HOLD'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get current price
    current_price = get_cached_price(ticker)

    # Create decision record
    decision = Decision.objects.create(
        portfolio=portfolio,
        ticker=ticker,
        action=action,
        shares=Decimal(str(shares)),
        price=Decimal(str(current_price)),
        strategy=strategy,
        reasoning=reasoning,
        recommendation=recommendation
    )

    return Response({
        'success': True,
        'message': f'Decision recorded: {action} {ticker}',
        'decision': {
            'ticker': decision.ticker,
            'action': decision.action,
            'shares': float(decision.shares),
            'price': float(decision.price),
            'timestamp': decision.timestamp.isoformat(),
            'reasoning': decision.reasoning,
            'recommendation': decision.recommendation
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_strategy_portfolio(request, strategy):
    """Get portfolio for a specific strategy"""
    user = get_or_create_demo_user()

    # Get or create portfolio
    portfolio, created = Portfolio.objects.get_or_create(
        user=user,
        defaults={'available_cash': Decimal('10000.00'), 'initial_cash': Decimal('10000.00')}
    )

    # Get holdings for this strategy
    holdings = portfolio.holdings.filter(strategy=strategy.lower(), shares__gt=0)

    # Strategy-specific stock portfolios (default holdings if none exist)
    if strategy.lower() == "secure":
        default_stocks = [
            {"ticker": "JNJ", "shares": 15, "avg_price": 155.50},
            {"ticker": "PG", "shares": 12, "avg_price": 145.30},
            {"ticker": "KO", "shares": 25, "avg_price": 58.20},
            {"ticker": "WMT", "shares": 10, "avg_price": 165.40},
            {"ticker": "VZ", "shares": 20, "avg_price": 38.75},
        ]
    elif strategy.lower() == "aggressive":
        default_stocks = [
            {"ticker": "NVDA", "shares": 5, "avg_price": 485.30},
            {"ticker": "TSLA", "shares": 8, "avg_price": 242.50},
            {"ticker": "AMD", "shares": 15, "avg_price": 128.60},
            {"ticker": "PLTR", "shares": 30, "avg_price": 28.40},
            {"ticker": "COIN", "shares": 12, "avg_price": 195.80},
        ]
    else:  # moderate
        default_stocks = [
            {"ticker": "AAPL", "shares": 10, "avg_price": 178.50},
            {"ticker": "MSFT", "shares": 8, "avg_price": 380.25},
            {"ticker": "V", "shares": 7, "avg_price": 258.30},
            {"ticker": "JPM", "shares": 12, "avg_price": 155.60},
            {"ticker": "DIS", "shares": 15, "avg_price": 92.40},
        ]

    # If no holdings exist, return default portfolio structure
    if not holdings.exists():
        portfolio_list = []
        for stock in default_stocks:
            current_price = get_cached_price(stock["ticker"])
            if current_price == 0:
                current_price = stock["avg_price"]  # Fallback to avg price

            total_value = current_price * stock["shares"]
            total_cost = stock["avg_price"] * stock["shares"]
            pnl = total_value - total_cost
            pnl_pct = (pnl / total_cost) * 100 if total_cost > 0 else 0

            portfolio_list.append({
                "ticker": stock["ticker"],
                "shares": stock["shares"],
                "avg_price": stock["avg_price"],
                "current_price": round(current_price, 2),
                "total_value": round(total_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "recommendation": "HOLD",
                "confidence": 0.75,
                "reasoning": "Default portfolio position"
            })
    else:
        # Use actual holdings from database
        portfolio_list = []
        for holding in holdings:
            current_price = get_cached_price(holding.ticker)
            if current_price == 0:
                current_price = float(holding.avg_price)

            total_value = current_price * float(holding.shares)
            total_cost = float(holding.avg_price) * float(holding.shares)
            pnl = total_value - total_cost
            pnl_pct = (pnl / total_cost) * 100 if total_cost > 0 else 0

            portfolio_list.append({
                "ticker": holding.ticker,
                "shares": float(holding.shares),
                "avg_price": float(holding.avg_price),
                "current_price": round(current_price, 2),
                "total_value": round(total_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "recommendation": "HOLD",
                "confidence": 0.75,
                "reasoning": "Current holding"
            })

    # Calculate portfolio totals
    total_value = sum(s["total_value"] for s in portfolio_list)
    total_pnl = sum(s["pnl"] for s in portfolio_list)
    total_cost = sum(s["avg_price"] * s["shares"] for s in portfolio_list)
    available_cash = float(portfolio.available_cash)
    initial_cash = float(portfolio.initial_cash)

    return Response({
        "strategy": strategy.lower(),
        "available_cash": round(available_cash, 2),
        "initial_cash": round(initial_cash, 2),
        "portfolio": portfolio_list,
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round((total_pnl / total_cost) * 100, 2) if total_cost > 0 else 0,
        "timestamp": timezone.now().isoformat(),
    })

from rest_framework import serializers
from .models import Portfolio, Holding, Trade
from users.models import User


class HoldingSerializer(serializers.ModelSerializer):
    """Serializer for Holding model with calculated fields"""
    current_price = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True)
    value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    pnl = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    pnl_pct = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)

    class Meta:
        model = Holding
        fields = [
            'id', 'ticker', 'shares', 'avg_price', 'strategy',
            'current_price', 'value', 'pnl', 'pnl_pct',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TradeSerializer(serializers.ModelSerializer):
    """Serializer for Trade model"""

    class Meta:
        model = Trade
        fields = [
            'id', 'ticker', 'action', 'shares', 'price',
            'total_amount', 'strategy', 'timestamp'
        ]
        read_only_fields = ['id', 'total_amount', 'timestamp']


class PortfolioSerializer(serializers.ModelSerializer):
    """Serializer for Portfolio model with holdings and calculated fields"""
    holdings = HoldingSerializer(many=True, read_only=True)
    total_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    holdings_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    total_pnl = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    total_pnl_pct = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Portfolio
        fields = [
            'id', 'user_email', 'available_cash', 'initial_cash',
            'total_value', 'holdings_value', 'total_pnl', 'total_pnl_pct',
            'holdings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PortfolioCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating portfolio capital"""
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)

    class Meta:
        model = Portfolio
        fields = ['amount']

    def validate_amount(self, value):
        """Validate that amount is positive"""
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        return value


class TradeExecuteSerializer(serializers.Serializer):
    """Serializer for executing trades"""
    ticker = serializers.CharField(max_length=10, required=True)
    action = serializers.ChoiceField(choices=['BUY', 'SELL'], required=True)
    shares = serializers.DecimalField(max_digits=15, decimal_places=4, required=True)
    strategy = serializers.ChoiceField(choices=['secure', 'moderate', 'aggressive'], required=True)

    def validate_ticker(self, value):
        """Validate ticker format"""
        return value.upper()

    def validate_shares(self, value):
        """Validate shares is positive"""
        if value <= 0:
            raise serializers.ValidationError("Shares must be greater than 0")
        return value

    def validate_action(self, value):
        """Normalize action to uppercase"""
        return value.upper()

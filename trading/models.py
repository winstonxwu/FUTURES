from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Portfolio(models.Model):
    """User's trading portfolio with virtual capital"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='portfolio')
    available_cash = models.DecimalField(max_digits=15, decimal_places=2, default=10000.00)
    initial_cash = models.DecimalField(max_digits=15, decimal_places=2, default=10000.00)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolios'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email}'s Portfolio - ${self.available_cash}"

    @property
    def total_value(self):
        """Calculate total portfolio value including cash and holdings"""
        holdings_value = sum(holding.value for holding in self.holdings.all())
        return float(self.available_cash) + holdings_value

    @property
    def holdings_value(self):
        """Calculate total value of all holdings"""
        return sum(holding.value for holding in self.holdings.all())

    @property
    def total_pnl(self):
        """Calculate total profit/loss"""
        return self.total_value - float(self.initial_cash)

    @property
    def total_pnl_pct(self):
        """Calculate total profit/loss percentage"""
        if self.initial_cash == 0:
            return 0
        return (self.total_pnl / float(self.initial_cash)) * 100


class Holding(models.Model):
    """User's stock holdings/positions"""
    STRATEGY_CHOICES = [
        ('secure', 'Secure'),
        ('moderate', 'Moderate'),
        ('aggressive', 'Aggressive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    ticker = models.CharField(max_length=10, db_index=True)
    shares = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    avg_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='moderate')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'holdings'
        ordering = ['-created_at']
        unique_together = ['portfolio', 'ticker', 'strategy']
        indexes = [
            models.Index(fields=['portfolio', 'ticker']),
            models.Index(fields=['ticker']),
        ]

    def __str__(self):
        return f"{self.portfolio.user.email} - {self.ticker} ({self.shares} shares)"

    @property
    def cost_basis(self):
        """Total cost of this holding"""
        return float(self.shares) * float(self.avg_price)

    def calculate_value(self, current_price):
        """Calculate current value of holding at given price"""
        return float(self.shares) * current_price

    def calculate_pnl(self, current_price):
        """Calculate profit/loss at given price"""
        return self.calculate_value(current_price) - self.cost_basis

    def calculate_pnl_pct(self, current_price):
        """Calculate profit/loss percentage at given price"""
        if self.avg_price == 0:
            return 0
        return ((current_price - float(self.avg_price)) / float(self.avg_price)) * 100


class Trade(models.Model):
    """Trade history for users"""
    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
    ]

    STRATEGY_CHOICES = [
        ('secure', 'Secure'),
        ('moderate', 'Moderate'),
        ('aggressive', 'Aggressive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='trades')
    ticker = models.CharField(max_length=10, db_index=True)
    action = models.CharField(max_length=4, choices=ACTION_CHOICES)
    shares = models.DecimalField(max_digits=15, decimal_places=4)
    price = models.DecimalField(max_digits=15, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'trades'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['portfolio', 'ticker']),
            models.Index(fields=['portfolio', 'timestamp']),
            models.Index(fields=['ticker', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.action} {self.shares} {self.ticker} @ ${self.price} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

    def save(self, *args, **kwargs):
        """Calculate total_amount on save"""
        if not self.total_amount:
            self.total_amount = float(self.shares) * float(self.price)
        super().save(*args, **kwargs)


class Decision(models.Model):
    """AI decision history for tracking user decisions and recommendations"""
    ACTION_CHOICES = [
        ('BUY', 'Buy'),
        ('SELL', 'Sell'),
        ('HOLD', 'Hold'),
    ]

    STRATEGY_CHOICES = [
        ('secure', 'Secure'),
        ('moderate', 'Moderate'),
        ('aggressive', 'Aggressive'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='decisions')
    ticker = models.CharField(max_length=10, db_index=True)
    action = models.CharField(max_length=4, choices=ACTION_CHOICES)
    shares = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES)
    reasoning = models.TextField(blank=True, null=True)
    recommendation = models.JSONField(default=dict, blank=True)  # Store full recommendation object
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'decisions'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['portfolio', 'strategy', 'timestamp']),
            models.Index(fields=['portfolio', 'ticker']),
            models.Index(fields=['strategy', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.action} {self.ticker} ({self.strategy}) - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

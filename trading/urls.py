from django.urls import path
from . import views

urlpatterns = [
    # More specific paths first to avoid conflicts
    path('portfolio/set-capital/', views.set_capital, name='set_capital'),
    path('portfolio/trade/', views.execute_trade, name='execute_trade'),
    path('portfolio/decision/', views.record_decision, name='record_decision'),
    path('portfolio/decisions/<str:strategy>/', views.get_decision_history, name='get_decision_history'),
    path('portfolio/<str:strategy>/', views.get_strategy_portfolio, name='get_strategy_portfolio'),
    path('portfolio/', views.get_portfolio, name='get_portfolio'),
    path('trades/', views.get_trade_history, name='get_trade_history'),
]

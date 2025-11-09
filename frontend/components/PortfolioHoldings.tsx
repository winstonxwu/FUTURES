'use client';

import { useState, useEffect } from 'react';

interface Holding {
  ticker: string;
  shares: number;
  avg_price: number;
  current_price: number;
  value: number;
  pnl: number;
  pnl_pct: number;
  strategy: string;
}

interface PortfolioData {
  starting_balance: number;
  available_cash: number;
  holdings_value: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings: Holding[];
}

export default function PortfolioHoldings() {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchPortfolio = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/portfolio');
      if (response.ok) {
        const data = await response.json();
        setPortfolio(data);
      }
    } catch (err) {
      console.error('Failed to fetch portfolio:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolio();

    // Listen for portfolio updates
    const handleUpdate = () => fetchPortfolio();
    window.addEventListener('portfolio-updated', handleUpdate);

    return () => window.removeEventListener('portfolio-updated', handleUpdate);
  }, []);

  if (loading) {
    return (
      <div className="glass-card rounded-2xl p-6 md:p-8">
        <div className="flex items-center justify-center py-8">
          <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  if (!portfolio || portfolio.holdings.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-6 md:p-8">
        <h2 className="text-2xl font-bold mb-6 flex items-center gap-3">
          <span className="text-3xl">📊</span>
          Portfolio Holdings
        </h2>
        <div className="text-center py-12">
          <div className="text-6xl mb-4">📭</div>
          <p className="text-xl text-gray-400 mb-2">No holdings yet</p>
          <p className="text-sm text-gray-500">Start trading to build your portfolio</p>
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-2xl p-6 md:p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold flex items-center gap-3">
          <span className="text-3xl">📊</span>
          Portfolio Holdings
        </h2>
        <div className="text-right">
          <div className="text-sm text-gray-400">Total Value</div>
          <div className="text-2xl font-bold">${portfolio.total_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
          <div className={`text-sm font-semibold ${portfolio.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {portfolio.total_pnl >= 0 ? '+' : ''}${portfolio.total_pnl.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})} ({portfolio.total_pnl_pct.toFixed(2)}%)
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-[var(--background-secondary)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-xs text-gray-400 mb-1">Available Cash</div>
          <div className="text-xl font-bold">${portfolio.available_cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </div>
        <div className="bg-[var(--background-secondary)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-xs text-gray-400 mb-1">Holdings Value</div>
          <div className="text-xl font-bold">${portfolio.holdings_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
        </div>
        <div className="bg-[var(--background-secondary)] rounded-xl p-4 border border-[var(--border-color)]">
          <div className="text-xs text-gray-400 mb-1">Positions</div>
          <div className="text-xl font-bold">{portfolio.holdings.length}</div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--border-accent)]">
              <th className="text-left py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">Ticker</th>
              <th className="text-right py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">Shares</th>
              <th className="text-right py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">Avg Price</th>
              <th className="text-right py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">Current</th>
              <th className="text-right py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">Value</th>
              <th className="text-right py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">P&L</th>
              <th className="text-left py-4 px-4 text-[var(--foreground-secondary)] font-semibold text-sm">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.holdings.map((holding) => (
              <tr key={holding.ticker} className="border-b border-[var(--border-color)] hover:bg-[var(--background-tertiary)] transition-colors">
                <td className="py-4 px-4">
                  <div className="font-bold text-lg">{holding.ticker}</div>
                </td>
                <td className="text-right py-4 px-4 font-semibold">{holding.shares}</td>
                <td className="text-right py-4 px-4 font-mono text-gray-400">${holding.avg_price.toFixed(2)}</td>
                <td className="text-right py-4 px-4 font-mono font-bold">${holding.current_price.toFixed(2)}</td>
                <td className="text-right py-4 px-4 font-semibold">${holding.value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td className="text-right py-4 px-4">
                  <div className={`font-bold font-mono ${holding.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {holding.pnl >= 0 ? '+' : ''}${holding.pnl.toFixed(2)}
                  </div>
                  <div className={`text-xs ${holding.pnl >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    ({holding.pnl_pct.toFixed(2)}%)
                  </div>
                </td>
                <td className="py-4 px-4">
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    holding.strategy === 'secure' ? 'bg-blue-500/20 text-blue-300' :
                    holding.strategy === 'moderate' ? 'bg-purple-500/20 text-purple-300' :
                    'bg-red-500/20 text-red-300'
                  }`}>
                    {holding.strategy}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

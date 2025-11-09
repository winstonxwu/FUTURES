'use client';

import React, { useState } from 'react';
import Carousel, { CarouselItem } from './Carousel';

interface PortfolioStock {
  ticker: string;
  shares: number;
  avg_price: number;
  current_price: number;
  total_value: number;
  pnl: number;
  pnl_pct: number;
  recommendation: string;
  confidence: number;
  reasoning: string;
}

interface PortfolioData {
  strategy: string;
  virtual_balance: number;
  available_cash: number;
  portfolio: PortfolioStock[];
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  timestamp: string;
}

interface StrategyCardsProps {
  onStrategySelect?: (strategy: 'secure' | 'moderate' | 'aggressive') => void;
}

interface Decision {
  ticker: string;
  action: string;
  shares: number;
  price: number;
  timestamp: string;
  recommendation: any;
}

interface AIDecision {
  ticker: string;
  action: string;
  shares: number;
  reasoning: string;
  full_decision: string;
}

export default function StrategyCards({ onStrategySelect }: StrategyCardsProps) {
  const [selectedStrategy, setSelectedStrategy] = useState<'secure' | 'moderate' | 'aggressive' | null>(null);
  const [portfolioData, setPortfolioData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [realAvailableCash, setRealAvailableCash] = useState<number | null>(null);
  const [decisionHistory, setDecisionHistory] = useState<Decision[]>([]);
  const [aiDecisions, setAiDecisions] = useState<{[key: string]: AIDecision}>({});
  const [loadingAI, setLoadingAI] = useState(false);

  const strategyItems: CarouselItem[] = [
    {
      id: 0,
      title: 'Secure',
      description: 'Conservative approach focusing on stable, blue-chip stocks with lower risk and dividend payments.',
      icon: <span style={{ fontSize: '32px' }}>🛡️</span>
    },
    {
      id: 1,
      title: 'Moderate',
      description: 'Balanced approach mixing growth potential with reasonable risk management and diversification.',
      icon: <span style={{ fontSize: '32px' }}>⚖️</span>
    },
    {
      id: 2,
      title: 'Aggressive',
      description: 'High-growth approach targeting maximum returns with higher risk tolerance in emerging sectors.',
      icon: <span style={{ fontSize: '32px' }}>🚀</span>
    }
  ];

  const fetchAIDecisions = async (stocks: PortfolioStock[], strategy: string) => {
    setLoadingAI(true);
    const decisions: {[key: string]: AIDecision} = {};

    try {
      // Fetch AI decision for each stock
      for (const stock of stocks) {
        try {
          const response = await fetch(`http://localhost:8000/api/ai/decision/${stock.ticker}?strategy=${strategy}`);
          if (response.ok) {
            const decision = await response.json();
            decisions[stock.ticker] = decision;
          }
        } catch (error) {
          console.error(`Error fetching AI decision for ${stock.ticker}:`, error);
        }
      }
    } catch (error) {
      console.error('Error fetching AI decisions:', error);
    } finally {
      setAiDecisions(decisions);
      setLoadingAI(false);
    }
  };

  const handleCardClick = async (idx: number) => {
    const strategies: ('secure' | 'moderate' | 'aggressive')[] = ['secure', 'moderate', 'aggressive'];
    const strategy = strategies[idx];

    setSelectedStrategy(strategy);
    setShowModal(true);
    setLoading(true);
    setAiDecisions({});

    // Fetch portfolio data, real available cash, and decision history
    try {
      // Fetch unified portfolio to get real available cash
      const unifiedResponse = await fetch(`http://localhost:8000/api/portfolio`);
      if (unifiedResponse.ok) {
        const unifiedData = await unifiedResponse.json();
        setRealAvailableCash(unifiedData.available_cash);
      }

      // Fetch decision history for this strategy
      const decisionsResponse = await fetch(`http://localhost:8000/api/portfolio/decisions/${strategy}`);
      if (decisionsResponse.ok) {
        const decisionsData = await decisionsResponse.json();
        setDecisionHistory(decisionsData.decisions || []);
      }

      // Fetch strategy-specific portfolio
      const response = await fetch(`http://localhost:8000/api/portfolio/${strategy}`);
      if (response.ok) {
        const data = await response.json();
        setPortfolioData(data);

        // Fetch AI decisions for each stock in the portfolio
        if (data.portfolio && data.portfolio.length > 0) {
          await fetchAIDecisions(data.portfolio, strategy);
        }
      } else {
        console.error('Failed to fetch portfolio');
        setPortfolioData(null);
      }
    } catch (error) {
      console.error('Error fetching portfolio:', error);
      setPortfolioData(null);
    } finally {
      setLoading(false);
    }

    onStrategySelect?.(strategy);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedStrategy(null);
    setPortfolioData(null);
  };

  const handleAction = async (ticker: string, action: string, stock: PortfolioStock) => {
    console.log(`${action} action for ${ticker}`);

    let shares = 0;

    // For SELL, check current holdings first
    if (action === 'SELL') {
      try {
        const portfolioResponse = await fetch('http://localhost:8000/api/portfolio');
        if (portfolioResponse.ok) {
          const portfolioData = await portfolioResponse.json();
          const holding = portfolioData.holdings.find((h: any) => h.ticker === ticker);

          if (!holding || holding.shares === 0) {
            alert(`You don't own any shares of ${ticker}`);
            return;
          }

          const sharesInput = prompt(`How many shares of ${ticker} would you like to sell?\n\nYou currently own: ${holding.shares} shares`);
          if (!sharesInput) return;

          shares = parseInt(sharesInput);
          if (isNaN(shares) || shares <= 0) {
            alert('Please enter a valid number of shares');
            return;
          }

          if (shares > holding.shares) {
            alert(`You only own ${holding.shares} shares of ${ticker}. Cannot sell ${shares} shares.`);
            return;
          }
        } else {
          alert('Failed to fetch portfolio holdings');
          return;
        }
      } catch (err) {
        console.error('Error fetching portfolio:', err);
        alert('Error checking holdings. Please try again.');
        return;
      }
    } else if (action === 'BUY') {
      const sharesInput = prompt(`How many shares of ${ticker} would you like to buy?`);
      if (!sharesInput) return;

      shares = parseInt(sharesInput);
      if (isNaN(shares) || shares <= 0) {
        alert('Please enter a valid number of shares');
        return;
      }
    }

    try {
      // Execute the trade action (BUY or SELL)
      if (action !== 'HOLD') {
        const tradeResponse = await fetch('http://localhost:8000/api/portfolio/trade', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            ticker,
            action,
            shares,
            strategy: selectedStrategy
          })
        });

        const result = await tradeResponse.json();

        if (tradeResponse.ok) {
          alert(result.message + `\n\nAvailable Cash: $${result.available_cash.toFixed(2)}`);

          // Emit custom event to notify main page to refresh
          window.dispatchEvent(new CustomEvent('portfolio-updated'));
        } else {
          alert(`Error: ${result.detail || 'Trade failed'}`);
          return;
        }
      } else {
        alert(`Decision recorded: Holding ${ticker}`);
      }

      // Refresh the portfolio and decision history
      if (selectedStrategy) {
        handleCardClick(['secure', 'moderate', 'aggressive'].indexOf(selectedStrategy));
      }
    } catch (error) {
      console.error('Error executing action:', error);
      alert('Error executing action. Please try again.');
    }
  };

  return (
    <>
      <div className="flex justify-center w-full">
        <Carousel
          items={strategyItems}
          baseWidth={600}
          autoplay={true}
          autoplayDelay={4000}
          pauseOnHover={true}
          loop={true}
          onItemClick={handleCardClick}
        />
      </div>

      {/* Recommendations Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">
                {selectedStrategy === 'secure' && '🛡️ Secure Strategy'}
                {selectedStrategy === 'moderate' && '⚖️ Moderate Strategy'}
                {selectedStrategy === 'aggressive' && '🚀 Aggressive Strategy'}
              </h2>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>

            <div className="modal-body">
              {loading ? (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Loading your {selectedStrategy} portfolio...</p>
                </div>
              ) : portfolioData ? (
                <div className="portfolio-view">
                  {/* Portfolio Summary */}
                  <div className="portfolio-summary">
                    <div className="summary-grid">
                      <div className="summary-item">
                        <span className="summary-label">Virtual Balance</span>
                        <span className="summary-value">${portfolioData.virtual_balance.toFixed(2)}</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Available Cash</span>
                        <span className="summary-value cash">${(realAvailableCash !== null ? realAvailableCash : portfolioData.available_cash).toFixed(2)}</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Portfolio Value</span>
                        <span className="summary-value">${portfolioData.total_value.toFixed(2)}</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Total P&L</span>
                        <span className={`summary-value ${portfolioData.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                          {portfolioData.total_pnl >= 0 ? '+' : ''}${portfolioData.total_pnl.toFixed(2)} ({portfolioData.total_pnl_pct.toFixed(2)}%)
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Decision History */}
                  {decisionHistory.length > 0 && (
                    <div className="decision-history">
                      <h3 className="history-header">Past Decisions</h3>
                      {decisionHistory.map((decision, idx) => (
                        <div key={idx} className="decision-card greyed-out">
                          <div className="decision-header">
                            <div className="decision-info">
                              <h4 className="decision-ticker">{decision.ticker}</h4>
                              <p className="decision-details">
                                {decision.action} {decision.shares > 0 ? `${decision.shares} shares` : ''} @ ${decision.price.toFixed(2)}
                                <span className="decision-timestamp"> • {new Date(decision.timestamp).toLocaleString()}</span>
                              </p>
                            </div>
                            <div className="decision-action-badge">
                              <span className={`action-badge ${decision.action.toLowerCase()}`}>
                                {decision.action}
                              </span>
                            </div>
                          </div>
                          {decision.recommendation && (
                            <p className="decision-reasoning">{decision.recommendation.reasoning}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Portfolio Stocks */}
                  <div className="portfolio-stocks">
                    <h3 className="stocks-header">Current Recommendations</h3>
                    {portfolioData.portfolio.map((stock, idx) => {
                      const aiDecision = aiDecisions[stock.ticker];
                      return (
                      <div key={idx} className="stock-card">
                        {/* AI Decision Section */}
                        {loadingAI && !aiDecision ? (
                          <div className="ai-decision-loading">
                            <div className="spinner-small"></div>
                            <p>Running AI analysis for {stock.ticker}...</p>
                          </div>
                        ) : aiDecision ? (
                          <div className="ai-decision">
                            <div className="ai-decision-header">
                              <span className="ai-label">🤖 AI Decision</span>
                              <span className={`ai-action ${aiDecision.action.toLowerCase()}`}>
                                {aiDecision.action}
                                {aiDecision.shares > 0 && ` ${aiDecision.shares} shares`}
                              </span>
                            </div>
                            <p className="ai-reasoning">{aiDecision.reasoning}</p>
                          </div>
                        ) : null}

                        <div className="stock-header">
                          <div className="stock-info">
                            <h4 className="stock-ticker">{stock.ticker}</h4>
                            <p className="stock-shares">{stock.shares} shares @ ${stock.avg_price.toFixed(2)}</p>
                          </div>
                          <div className="stock-performance">
                            <div className="stock-price">${stock.current_price.toFixed(2)}</div>
                            <div className={`stock-pnl ${stock.pnl >= 0 ? 'positive' : 'negative'}`}>
                              {stock.pnl >= 0 ? '+' : ''}${stock.pnl.toFixed(2)} ({stock.pnl_pct.toFixed(2)}%)
                            </div>
                          </div>
                        </div>

                        <div className="stock-recommendation">
                          <div className="rec-badge">{stock.recommendation}</div>
                          <div className="rec-confidence">{(stock.confidence * 100).toFixed(0)}% confident</div>
                        </div>

                        <p className="stock-reasoning">{stock.reasoning}</p>

                        <div className="stock-actions">
                          <button
                            className="action-btn buy-btn"
                            onClick={() => handleAction(stock.ticker, 'BUY', stock)}
                          >
                            Buy
                          </button>
                          <button
                            className="action-btn hold-btn"
                            onClick={() => handleAction(stock.ticker, 'HOLD', stock)}
                          >
                            Hold
                          </button>
                          <button
                            className="action-btn sell-btn"
                            onClick={() => handleAction(stock.ticker, 'SELL', stock)}
                          >
                            Sell
                          </button>
                        </div>
                      </div>
                    );
                    })}
                  </div>
                </div>
              ) : (
                <div className="no-recommendations">
                  <p>Unable to load portfolio. Please try again later.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 1rem;
        }

        .modal-content {
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          border-radius: 16px;
          max-width: 800px;
          width: 100%;
          max-height: 90vh;
          overflow-y: auto;
          border: 2px solid rgba(255, 255, 255, 0.1);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1.5rem 2rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .modal-title {
          font-size: 1.5rem;
          font-weight: bold;
          color: white;
          margin: 0;
        }

        .modal-close {
          background: none;
          border: none;
          color: white;
          font-size: 2rem;
          cursor: pointer;
          padding: 0;
          width: 2rem;
          height: 2rem;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
          transition: background 0.2s;
        }

        .modal-close:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .modal-body {
          padding: 2rem;
        }

        .loading-state {
          text-align: center;
          padding: 3rem 0;
          color: white;
        }

        .spinner {
          width: 50px;
          height: 50px;
          border: 4px solid rgba(255, 255, 255, 0.1);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 1rem;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        .recommendations-list {
          color: white;
        }

        .recommendations-intro {
          margin-bottom: 1.5rem;
          font-size: 1rem;
          color: rgba(255, 255, 255, 0.8);
        }

        .recommendation-card {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          padding: 1.5rem;
          margin-bottom: 1rem;
        }

        .rec-header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          margin-bottom: 1rem;
        }

        .rec-ticker {
          font-size: 1.25rem;
          font-weight: bold;
          margin: 0 0 0.25rem 0;
          color: white;
        }

        .rec-name {
          font-size: 0.9rem;
          color: rgba(255, 255, 255, 0.6);
          margin: 0;
        }

        .rec-confidence {
          text-align: right;
        }

        .confidence-label {
          display: block;
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.6);
          margin-bottom: 0.25rem;
        }

        .confidence-value {
          display: block;
          font-size: 1.25rem;
          font-weight: bold;
          color: #4ade80;
        }

        .rec-recommendation {
          background: rgba(74, 222, 128, 0.1);
          border: 1px solid rgba(74, 222, 128, 0.3);
          padding: 0.75rem;
          border-radius: 8px;
          margin-bottom: 1rem;
          color: #4ade80;
        }

        .rec-reasoning {
          font-size: 0.9rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.8);
          margin: 0;
        }

        .no-recommendations {
          text-align: center;
          padding: 3rem 0;
          color: rgba(255, 255, 255, 0.6);
        }

        /* Portfolio View Styles */
        .portfolio-view {
          color: white;
        }

        .portfolio-summary {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          padding: 1.5rem;
          margin-bottom: 2rem;
        }

        .summary-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 1rem;
        }

        @media (max-width: 640px) {
          .summary-grid {
            grid-template-columns: 1fr;
          }
        }

        .summary-item {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .summary-label {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .summary-value {
          font-size: 1.25rem;
          font-weight: bold;
          color: white;
        }

        .summary-value.cash {
          color: #60a5fa;
        }

        .summary-value.positive {
          color: #4ade80;
        }

        .summary-value.negative {
          color: #f87171;
        }

        .portfolio-stocks {
          margin-top: 1.5rem;
        }

        .stocks-header {
          font-size: 1.25rem;
          font-weight: bold;
          color: white;
          margin-bottom: 1rem;
        }

        .stock-card {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          padding: 1.5rem;
          margin-bottom: 1rem;
          transition: all 0.3s ease;
        }

        .stock-card:hover {
          background: rgba(255, 255, 255, 0.08);
          border-color: rgba(255, 255, 255, 0.2);
          transform: translateY(-2px);
        }

        .stock-header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          margin-bottom: 1rem;
        }

        .stock-info {
          flex: 1;
        }

        .stock-ticker {
          font-size: 1.5rem;
          font-weight: bold;
          color: white;
          margin: 0 0 0.25rem 0;
        }

        .stock-shares {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
          margin: 0;
        }

        .stock-performance {
          text-align: right;
        }

        .stock-price {
          font-size: 1.25rem;
          font-weight: bold;
          color: white;
          margin-bottom: 0.25rem;
        }

        .stock-pnl {
          font-size: 0.875rem;
          font-weight: 600;
        }

        .stock-pnl.positive {
          color: #4ade80;
        }

        .stock-pnl.negative {
          color: #f87171;
        }

        .stock-recommendation {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 1rem;
          padding: 0.75rem;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 8px;
        }

        .rec-badge {
          font-weight: bold;
          font-size: 0.875rem;
          padding: 0.5rem 1rem;
          border-radius: 6px;
          background: rgba(74, 222, 128, 0.15);
          color: #4ade80;
          border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .rec-confidence {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.7);
        }

        .stock-reasoning {
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.8);
          margin: 0 0 1rem 0;
          padding: 0.75rem;
          background: rgba(255, 255, 255, 0.02);
          border-radius: 6px;
          border-left: 3px solid rgba(255, 255, 255, 0.2);
        }

        .stock-actions {
          display: flex;
          gap: 0.75rem;
          justify-content: flex-end;
        }

        .action-btn {
          padding: 0.625rem 1.5rem;
          border-radius: 8px;
          font-weight: 600;
          font-size: 0.875rem;
          border: none;
          cursor: pointer;
          transition: all 0.2s ease;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .action-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        .action-btn:active {
          transform: translateY(0);
        }

        .buy-btn {
          background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
          color: white;
        }

        .buy-btn:hover {
          background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
        }

        .hold-btn {
          background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
          color: white;
        }

        .hold-btn:hover {
          background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        }

        .sell-btn {
          background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
          color: white;
        }

        .sell-btn:hover {
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        }

        /* Decision History Styles */
        .decision-history {
          margin: 2rem 0;
          padding-bottom: 1.5rem;
          border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }

        .history-header {
          font-size: 1.25rem;
          font-weight: bold;
          color: rgba(255, 255, 255, 0.8);
          margin-bottom: 1rem;
        }

        .decision-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          padding: 1.25rem;
          margin-bottom: 0.75rem;
          transition: all 0.3s ease;
        }

        .decision-card.greyed-out {
          opacity: 0.5;
          filter: grayscale(0.5);
        }

        .decision-card.greyed-out:hover {
          opacity: 0.7;
          background: rgba(255, 255, 255, 0.05);
        }

        .decision-header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          margin-bottom: 0.75rem;
        }

        .decision-info {
          flex: 1;
        }

        .decision-ticker {
          font-size: 1.25rem;
          font-weight: bold;
          color: white;
          margin: 0 0 0.25rem 0;
        }

        .decision-details {
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.6);
          margin: 0;
        }

        .decision-timestamp {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.4);
        }

        .decision-action-badge {
          display: flex;
          align-items: center;
        }

        .action-badge {
          padding: 0.5rem 1rem;
          border-radius: 6px;
          font-weight: bold;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .action-badge.buy {
          background: rgba(74, 222, 128, 0.15);
          color: #4ade80;
          border: 1px solid rgba(74, 222, 128, 0.3);
        }

        .action-badge.hold {
          background: rgba(96, 165, 250, 0.15);
          color: #60a5fa;
          border: 1px solid rgba(96, 165, 250, 0.3);
        }

        .action-badge.sell {
          background: rgba(248, 113, 113, 0.15);
          color: #f87171;
          border: 1px solid rgba(248, 113, 113, 0.3);
        }

        .decision-reasoning {
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.6);
          margin: 0;
          padding: 0.75rem;
          background: rgba(255, 255, 255, 0.02);
          border-radius: 6px;
          border-left: 3px solid rgba(255, 255, 255, 0.15);
        }

        /* AI Decision Styles */
        .ai-decision {
          background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(99, 102, 241, 0.15) 100%);
          border: 2px solid rgba(139, 92, 246, 0.4);
          border-radius: 12px;
          padding: 1.25rem;
          margin-bottom: 1.5rem;
        }

        .ai-decision-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .ai-label {
          font-size: 0.875rem;
          font-weight: 600;
          color: rgba(139, 92, 246, 1);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .ai-action {
          padding: 0.5rem 1.25rem;
          border-radius: 8px;
          font-weight: bold;
          font-size: 1rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .ai-action.buy {
          background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
          color: white;
        }

        .ai-action.hold {
          background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
          color: white;
        }

        .ai-action.sell {
          background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
          color: white;
        }

        .ai-reasoning {
          font-size: 0.875rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.9);
          margin: 0;
        }

        .ai-decision-loading {
          text-align: center;
          padding: 2rem;
          color: rgba(255, 255, 255, 0.6);
        }

        .spinner-small {
          width: 30px;
          height: 30px;
          border: 3px solid rgba(255, 255, 255, 0.1);
          border-top-color: rgba(139, 92, 246, 1);
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 0.75rem;
        }
      `}</style>
    </>
  );
}

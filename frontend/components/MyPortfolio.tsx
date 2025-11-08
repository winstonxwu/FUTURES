'use client';

import React, { useState, useEffect } from 'react';

interface Holding {
  ticker: string;
  shares: number;
  avg_price: number;
  current_price: number;
  total_value: number;
  pnl: number;
  pnl_pct: number;
  strategy: string;
}

interface PortfolioData {
  starting_balance: number;
  available_cash: number;
  portfolio_value: number;
  total_account_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  holdings: Holding[];
  trade_count: number;
}

export default function MyPortfolio() {
  const [showModal, setShowModal] = useState(false);
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/portfolio');
      if (response.ok) {
        const data = await response.json();
        setPortfolio(data);
      } else {
        console.error('Failed to fetch portfolio');
      }
    } catch (error) {
      console.error('Error fetching portfolio:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setShowModal(true);
    fetchPortfolio();
  };

  const handleClose = () => {
    setShowModal(false);
  };

  return (
    <>
      <button
        onClick={handleOpen}
        className="my-portfolio-btn"
      >
        💼 My Portfolio
      </button>

      {showModal && (
        <div className="modal-overlay" onClick={handleClose}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">💼 My Portfolio</h2>
              <button className="modal-close" onClick={handleClose}>×</button>
            </div>

            <div className="modal-body">
              {loading ? (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Loading your portfolio...</p>
                </div>
              ) : portfolio ? (
                <div className="portfolio-view">
                  {/* Portfolio Summary */}
                  <div className="portfolio-summary">
                    <div className="summary-grid">
                      <div className="summary-item">
                        <span className="summary-label">Starting Balance</span>
                        <span className="summary-value">${portfolio.starting_balance.toFixed(2)}</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Available Cash</span>
                        <span className="summary-value cash">${portfolio.available_cash.toFixed(2)}</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Portfolio Value</span>
                        <span className="summary-value">${portfolio.portfolio_value.toFixed(2)}</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Total Account Value</span>
                        <span className={`summary-value ${portfolio.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                          ${portfolio.total_account_value.toFixed(2)}
                        </span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Total P&L</span>
                        <span className={`summary-value ${portfolio.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                          {portfolio.total_pnl >= 0 ? '+' : ''}${portfolio.total_pnl.toFixed(2)} ({portfolio.total_pnl_pct.toFixed(2)}%)
                        </span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-label">Total Trades</span>
                        <span className="summary-value">{portfolio.trade_count}</span>
                      </div>
                    </div>
                  </div>

                  {/* Holdings */}
                  {portfolio.holdings.length > 0 ? (
                    <div className="portfolio-stocks">
                      <h3 className="stocks-header">Your Holdings</h3>
                      {portfolio.holdings.map((holding, idx) => (
                        <div key={idx} className="stock-card">
                          <div className="stock-header">
                            <div className="stock-info">
                              <h4 className="stock-ticker">{holding.ticker}</h4>
                              <p className="stock-shares">
                                {holding.shares} shares @ ${holding.avg_price.toFixed(2)}
                                <span className="stock-strategy"> • {holding.strategy}</span>
                              </p>
                            </div>
                            <div className="stock-performance">
                              <div className="stock-price">${holding.current_price.toFixed(2)}</div>
                              <div className={`stock-pnl ${holding.pnl >= 0 ? 'positive' : 'negative'}`}>
                                {holding.pnl >= 0 ? '+' : ''}${holding.pnl.toFixed(2)} ({holding.pnl_pct.toFixed(2)}%)
                              </div>
                            </div>
                          </div>
                          <div className="holding-value">
                            <span className="value-label">Total Value:</span>
                            <span className="value-amount">${holding.total_value.toFixed(2)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="no-holdings">
                      <p>No holdings yet. Start trading by selecting a strategy!</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="no-data">
                  <p>Unable to load portfolio. Please try again.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .my-portfolio-btn {
          position: fixed;
          top: 20px;
          right: 20px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 12px;
          font-weight: 600;
          font-size: 16px;
          cursor: pointer;
          z-index: 999;
          box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
          transition: all 0.3s ease;
        }

        .my-portfolio-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }

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
          max-width: 900px;
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
          grid-template-columns: repeat(3, 1fr);
          gap: 1.5rem;
        }

        @media (max-width: 768px) {
          .summary-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 480px) {
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

        .stock-strategy {
          color: rgba(255, 255, 255, 0.4);
          text-transform: capitalize;
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

        .holding-value {
          display: flex;
          justify-content: space-between;
          padding-top: 1rem;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .value-label {
          color: rgba(255, 255, 255, 0.6);
          font-size: 0.875rem;
        }

        .value-amount {
          color: white;
          font-weight: 600;
        }

        .no-holdings,
        .no-data {
          text-align: center;
          padding: 3rem 0;
          color: rgba(255, 255, 255, 0.6);
        }
      `}</style>
    </>
  );
}

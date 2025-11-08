'use client';

import { useState } from 'react';
import { apiClient, TradeRequest, TradeResponse } from '@/lib/api-client';
import Link from 'next/link';

export default function TradesPage() {
  const [formData, setFormData] = useState<TradeRequest>({
    ticker: '',
    action: 'BUY',
    s_final: 0.5,
    quantity: undefined,
    reason: '',
  });
  const [response, setResponse] = useState<TradeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const result = await apiClient.executeTrade(formData);
      setResponse(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade execution failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <Link href="/" className="text-blue-400 hover:text-blue-300 mb-4 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-4xl font-bold">Execute Trade</h1>
        </div>

        <div className="bg-gray-800 rounded-lg shadow-xl p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium mb-2">Ticker Symbol</label>
              <input
                type="text"
                value={formData.ticker}
                onChange={(e) => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="AAPL"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Action</label>
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, action: 'BUY' })}
                  className={`flex-1 py-3 rounded-lg font-semibold transition ${
                    formData.action === 'BUY'
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  BUY
                </button>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, action: 'SELL' })}
                  className={`flex-1 py-3 rounded-lg font-semibold transition ${
                    formData.action === 'SELL'
                      ? 'bg-red-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  SELL
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Investment Score (s_final): {formData.s_final}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.01"
                value={formData.s_final}
                onChange={(e) => setFormData({ ...formData, s_final: parseFloat(e.target.value) })}
                className="w-full"
              />
              <p className="text-xs text-gray-400 mt-1">
                Higher score = higher conviction (affects position sizing)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">
                Quantity (optional - leave blank for auto-sizing)
              </label>
              <input
                type="number"
                value={formData.quantity || ''}
                onChange={(e) =>
                  setFormData({ ...formData, quantity: e.target.value ? parseFloat(e.target.value) : undefined })
                }
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Auto"
                step="0.01"
                min="0"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2">Reason</label>
              <input
                type="text"
                value={formData.reason}
                onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., high_conviction_signal"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Executing...' : `Execute ${formData.action} Order`}
            </button>
          </form>

          {error && (
            <div className="mt-6 p-4 bg-red-900/50 border border-red-700 rounded-lg">
              <p className="text-red-400 font-semibold">Error:</p>
              <p className="text-red-300">{error}</p>
            </div>
          )}

          {response && (
            <div
              className={`mt-6 p-4 rounded-lg border ${
                response.success
                  ? 'bg-green-900/50 border-green-700'
                  : 'bg-red-900/50 border-red-700'
              }`}
            >
              <p className={`font-semibold mb-2 ${response.success ? 'text-green-400' : 'text-red-400'}`}>
                {response.success ? 'Trade Executed Successfully' : 'Trade Failed'}
              </p>
              <div className="space-y-1 text-sm">
                <p>Order ID: {response.order_id || 'N/A'}</p>
                <p>Ticker: {response.ticker}</p>
                <p>Action: {response.action}</p>
                <p>Quantity: {response.quantity}</p>
                <p>Price: ${response.price?.toFixed(2) || 'N/A'}</p>
                <p>Message: {response.message}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

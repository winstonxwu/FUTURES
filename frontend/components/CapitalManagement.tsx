'use client';

import { useState } from 'react';

interface CapitalManagementProps {
  currentCapital: number;
  onCapitalSet: () => void;
}

export default function CapitalManagement({ currentCapital, onCapitalSet }: CapitalManagementProps) {
  const [amount, setAmount] = useState(10000);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [showModal, setShowModal] = useState(false);

  const presetAmounts = [5000, 10000, 25000, 50000, 100000];

  const handleSetCapital = async () => {
    setLoading(true);
    setMessage('');

    try {
      const response = await fetch('http://localhost:8000/api/portfolio/set-capital', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ amount }),
      });

      if (!response.ok) {
        throw new Error('Failed to set capital');
      }

      const data = await response.json();
      setMessage(data.message);
      setShowModal(false);
      onCapitalSet();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to set capital');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-bold hover:from-green-600 hover:to-emerald-600 transition-all shadow-lg shadow-green-500/25 flex items-center gap-2"
      >
        <span>💵</span>
        Set Virtual Capital
      </button>

      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="glass-card rounded-2xl p-8 max-w-md w-full border-2 border-green-500/30">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-2xl font-bold">Set Virtual Capital</h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-white transition-colors text-2xl"
              >
                ×
              </button>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-semibold mb-3 text-gray-300">
                Amount (USD)
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-2xl font-bold text-gray-400">
                  $
                </span>
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
                  className="w-full pl-10 pr-4 py-4 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-green-500 focus:ring-4 focus:ring-green-500/20 transition-all text-2xl font-bold"
                  min="0"
                  step="1000"
                />
              </div>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-semibold mb-3 text-gray-300">
                Quick Select
              </label>
              <div className="grid grid-cols-3 gap-2">
                {presetAmounts.map((preset) => (
                  <button
                    key={preset}
                    onClick={() => setAmount(preset)}
                    className={`px-4 py-3 rounded-lg font-semibold transition-all ${
                      amount === preset
                        ? 'bg-green-500 text-white shadow-lg'
                        : 'bg-[var(--background-tertiary)] text-gray-400 hover:bg-[var(--border-accent)]'
                    }`}
                  >
                    ${(preset / 1000).toFixed(0)}k
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-yellow-500/10 border-2 border-yellow-500/30 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div className="flex-1">
                  <p className="text-yellow-300 text-sm font-semibold mb-1">Warning</p>
                  <p className="text-yellow-200/80 text-sm">
                    This will reset your portfolio and clear all current holdings and trade history.
                  </p>
                </div>
              </div>
            </div>

            {message && (
              <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-300 text-sm">
                {message}
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 px-6 py-3 bg-[var(--background-tertiary)] text-gray-300 rounded-xl font-bold hover:bg-[var(--border-accent)] transition-all"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleSetCapital}
                className="flex-1 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-500 text-white rounded-xl font-bold hover:from-green-600 hover:to-emerald-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-500/25"
                disabled={loading}
              >
                {loading ? 'Setting...' : 'Confirm & Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

'use client';

import { useState } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';

const RippleGrid = dynamic(() => import('@/components/RippleGrid'), { ssr: false });

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface SimulationData {
  date: string;
  action: string;
  qty: number;
  exec_price: number;
  close_price: number;
  cash: number;
  shares: number;
  portfolio_value: number;
  daily_pnl: number;
}

interface SimulationResult {
  ticker: string;
  strategy: string;
  initial_cash: number;
  final_value: number;
  total_return: number;
  total_return_pct: number;
  num_trades: number;
  simulation_data: SimulationData[];
}

export default function SimulationPage() {
  const [ticker, setTicker] = useState('META');
  const [initialCash, setInitialCash] = useState(10000);
  const [strategy, setStrategy] = useState<'secure' | 'moderate' | 'aggressive'>('moderate');
  const [loading, setLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setLoadingProgress(0);
    setError(null);
    setResult(null);

    // Simulate progress updates
    const progressInterval = setInterval(() => {
      setLoadingProgress(prev => {
        if (prev >= 90) return prev;
        return prev + Math.random() * 15;
      });
    }, 500);

    try {
      const response = await fetch(`http://localhost:8000/api/simulation/run?ticker=${ticker}&initial_cash=${initialCash}&strategy=${strategy}`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Simulation failed');
      }

      const data = await response.json();
      setLoadingProgress(100);
      setTimeout(() => {
        setResult(data);
        setLoading(false);
      }, 300);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
      setLoading(false);
    } finally {
      clearInterval(progressInterval);
    }
  };

  const chartData = result ? {
    labels: result.simulation_data.map(d => d.date),
    datasets: [
      {
        label: 'Portfolio Value',
        data: result.simulation_data.map(d => d.portfolio_value),
        borderColor: 'rgb(139, 92, 246)',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.4,
      },
      {
        label: 'Initial Cash',
        data: result.simulation_data.map(() => result.initial_cash),
        borderColor: 'rgba(255, 255, 255, 0.3)',
        backgroundColor: 'transparent',
        borderDash: [5, 5],
        pointRadius: 0,
      }
    ]
  } : null;

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: 'white',
          font: {
            size: 12
          }
        }
      },
      title: {
        display: true,
        text: 'Portfolio Value Over Time (2024)',
        color: 'white',
        font: {
          size: 16,
          weight: 'bold' as const
        }
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD'
              }).format(context.parsed.y);
            }
            return label;
          }
        }
      }
    },
    scales: {
      y: {
        ticks: {
          color: 'rgba(255, 255, 255, 0.8)',
          callback: function(value: any) {
            return '$' + value.toLocaleString();
          }
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)'
        }
      },
      x: {
        ticks: {
          color: 'rgba(255, 255, 255, 0.8)',
          maxRotation: 45,
          minRotation: 45
        },
        grid: {
          color: 'rgba(255, 255, 255, 0.1)'
        }
      }
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-4 md:p-8 relative">
      {/* RippleGrid Background */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <RippleGrid
          gridColor="#8b5cf6"
          rippleIntensity={0.08}
          gridSize={8.0}
          gridThickness={12.0}
          fadeDistance={1.8}
          vignetteStrength={2.5}
          glowIntensity={0.15}
          opacity={0.4}
          mouseInteraction={true}
          mouseInteractionRadius={1.2}
        />
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        <div className="mb-10 md:mb-16 fade-in-up">
          <Link href="/" className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 mb-8 transition-colors group text-lg">
            <span className="group-hover:-translate-x-1 transition-transform">←</span>
            Back to Dashboard
          </Link>
          <h1 className="text-6xl md:text-7xl lg:text-8xl font-black gradient-text mb-4 tracking-tight">
            Trading Simulation
          </h1>
          <p className="text-[var(--foreground-secondary)] text-xl md:text-2xl font-medium">
            Run historical backtests on 2024 data with AI-powered strategies
          </p>
        </div>

        <div className="glass-card rounded-2xl p-6 md:p-10 mb-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-semibold mb-3">
                  Ticker Symbol
                </label>
                <input
                  type="text"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-purple-500 focus:ring-4 focus:ring-purple-500/20 transition-all font-bold uppercase"
                  placeholder="e.g., META"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-3">
                  Initial Cash
                </label>
                <input
                  type="number"
                  value={initialCash}
                  onChange={(e) => setInitialCash(parseFloat(e.target.value))}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-purple-500 focus:ring-4 focus:ring-purple-500/20 transition-all no-spinner"
                  min="1000"
                  step="1000"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-3">
                  Strategy
                </label>
                <select
                  value={strategy}
                  onChange={(e) => setStrategy(e.target.value as 'secure' | 'moderate' | 'aggressive')}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-purple-500 focus:ring-4 focus:ring-purple-500/20 transition-all"
                >
                  <option value="secure">🛡️ Secure</option>
                  <option value="moderate">⚖️ Moderate</option>
                  <option value="aggressive">🚀 Aggressive</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-gradient-to-r from-purple-500 to-blue-500 text-white rounded-xl font-bold text-lg hover:from-purple-600 hover:to-blue-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-purple-500/25"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-5 h-5 border-3 border-white border-t-transparent rounded-full animate-spin"></div>
                  Running Simulation...
                </span>
              ) : (
                '🎯 Run Simulation'
              )}
            </button>
          </form>
        </div>

        {/* Loading Progress Bar */}
        {loading && (
          <div className="glass-card rounded-2xl p-8 mb-8 bg-gradient-to-br from-purple-500/5 to-blue-500/5 border-2 border-purple-500/30">
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xl font-bold text-white">Processing Simulation...</h3>
                <span className="text-lg font-mono text-purple-300">{Math.round(loadingProgress)}%</span>
              </div>

              <div className="relative h-4 bg-gray-800/50 rounded-full overflow-hidden backdrop-blur-sm">
                <div
                  className="absolute top-0 left-0 h-full bg-gradient-to-r from-purple-500 via-blue-500 to-purple-600 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${loadingProgress}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"></div>
                </div>
              </div>

              <div className="flex items-center gap-3 text-sm text-gray-400">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
                  <span>Downloading historical data</span>
                </div>
                <span>•</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse animation-delay-200"></div>
                  <span>Running AI analysis</span>
                </div>
                <span>•</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse animation-delay-400"></div>
                  <span>Calculating returns</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="glass-card rounded-2xl p-6 mb-8 bg-red-500/10 border-2 border-red-500/50">
            <div className="flex items-start gap-3">
              <div className="text-2xl">⚠️</div>
              <div className="flex-1">
                <p className="text-red-400 font-bold text-lg mb-1">Simulation Failed</p>
                <p className="text-red-300">{error}</p>
              </div>
            </div>
          </div>
        )}

        {result && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
              <div className="glass-card rounded-xl p-6">
                <div className="text-sm text-[var(--foreground-secondary)] mb-2">Ticker</div>
                <div className="text-3xl font-bold">{result.ticker}</div>
              </div>
              <div className="glass-card rounded-xl p-6">
                <div className="text-sm text-[var(--foreground-secondary)] mb-2">Total Trades</div>
                <div className="text-3xl font-bold">{result.num_trades}</div>
              </div>
              <div className="glass-card rounded-xl p-6">
                <div className="text-sm text-[var(--foreground-secondary)] mb-2">Final Value</div>
                <div className="text-3xl font-bold">${result.final_value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
              </div>
              <div className="glass-card rounded-xl p-6">
                <div className="text-sm text-[var(--foreground-secondary)] mb-2">Total Return</div>
                <div className={`text-3xl font-bold ${result.total_return >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {result.total_return >= 0 ? '+' : ''}${result.total_return.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                  <span className="text-lg ml-2">({result.total_return_pct.toFixed(2)}%)</span>
                </div>
              </div>
            </div>

            <div className="glass-card rounded-2xl p-6 md:p-8">
              <div style={{ height: '400px' }}>
                {chartData && <Line data={chartData} options={chartOptions} />}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

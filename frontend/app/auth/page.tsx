'use client';

import { useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import Link from 'next/link';

export default function AuthPage() {
  const { login, signup } = useAuth();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showSignupModal, setShowSignupModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [signupData, setSignupData] = useState({ email: '', password: '', confirmPassword: '', name: '' });

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await login(loginData.email, loginData.password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    if (signupData.password !== signupData.confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    if (signupData.password.length < 8) {
      setError('Password must be at least 8 characters');
      setLoading(false);
      return;
    }

    try {
      await signup(signupData.email, signupData.password, signupData.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Animated background */}
      <div className="fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute top-0 -left-40 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 -right-40 w-80 h-80 bg-purple-500/10 rounded-full blur-3xl"></div>
      </div>

      {/* Navigation Bar */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass-card border-b border-[var(--border-color)]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold text-white">
            ValueCell AI Trader
          </Link>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowLoginModal(true)}
              className="px-5 py-2 text-white hover:text-gray-300 transition-colors font-medium"
            >
              Log In
            </button>
            <button
              onClick={() => setShowSignupModal(true)}
              className="px-5 py-2 bg-white text-black rounded-full font-semibold hover:bg-gray-200 transition-all"
            >
              Sign Up
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="min-h-screen flex items-center justify-center px-6 pt-20">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-6xl md:text-7xl font-bold text-white mb-6 fade-in-up">
            The Future of Trading is Here
          </h1>
          <p className="text-xl md:text-2xl text-[var(--foreground-secondary)] mb-8 fade-in-up">
            Powered by cutting-edge Large Language Models
          </p>
          <div className="w-20 h-1 bg-white mx-auto"></div>
        </div>
      </section>

      {/* Vision Section */}
      <section className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-8 text-center">
            Why LLM Trading?
          </h2>
          <div className="space-y-6 text-lg md:text-xl text-[var(--foreground-secondary)] leading-relaxed">
            <p>
              Traditional algorithmic trading relies on rigid rules and predefined strategies.
              But the market is dynamic, complex, and constantly evolving.
            </p>
            <p>
              Large Language Models bring unprecedented adaptability to trading. They can analyze
              news sentiment, understand market context, and make nuanced decisions that go beyond
              simple technical indicators.
            </p>
            <p className="text-white font-semibold">
              ValueCell AI Trader harnesses this power to give you an edge in the market.
            </p>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-16 text-center">
            Built for the Future
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="glass-card p-8 rounded-2xl">
              <div className="text-4xl mb-4">🧠</div>
              <h3 className="text-2xl font-bold text-white mb-4">AI-Powered Decisions</h3>
              <p className="text-[var(--foreground-secondary)]">
                Our LLM analyzes market sentiment, news, and technical data to make informed trading decisions.
              </p>
            </div>
            <div className="glass-card p-8 rounded-2xl">
              <div className="text-4xl mb-4">⚡</div>
              <h3 className="text-2xl font-bold text-white mb-4">Real-Time Execution</h3>
              <p className="text-[var(--foreground-secondary)]">
                Execute trades instantly with our optimized infrastructure and automated position management.
              </p>
            </div>
            <div className="glass-card p-8 rounded-2xl">
              <div className="text-4xl mb-4">📊</div>
              <h3 className="text-2xl font-bold text-white mb-4">Advanced Analytics</h3>
              <p className="text-[var(--foreground-secondary)]">
                Track performance, analyze positions, and optimize your strategy with detailed insights.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="min-h-screen flex items-center justify-center px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-5xl md:text-6xl font-bold text-white mb-12">
            Join The Movement Now
          </h2>
          <p className="text-xl text-[var(--foreground-secondary)] mb-12">
            Be part of the next generation of algorithmic traders
          </p>
          <button
            onClick={() => setShowSignupModal(true)}
            className="px-12 py-5 bg-white text-black rounded-full text-xl font-bold hover:bg-gray-200 transition-all hover:scale-105"
          >
            Get Started Today
          </button>
        </div>
      </section>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-card rounded-2xl p-8 max-w-md w-full relative">
            <button
              onClick={() => {
                setShowLoginModal(false);
                setError(null);
              }}
              className="absolute top-4 right-4 text-2xl text-[var(--foreground-secondary)] hover:text-white"
            >
              ×
            </button>
            <h2 className="text-3xl font-bold text-white mb-6">Log In</h2>
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-2 text-white">Email</label>
                <input
                  type="email"
                  value={loginData.email}
                  onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-white transition-all text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2 text-white">Password</label>
                <input
                  type="password"
                  value={loginData.password}
                  onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-white transition-all text-white"
                  required
                />
              </div>
              {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-400 text-sm">
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-white text-black rounded-xl font-bold hover:bg-gray-200 transition-all disabled:opacity-50"
              >
                {loading ? 'Logging in...' : 'Log In'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Signup Modal */}
      {showSignupModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-card rounded-2xl p-8 max-w-md w-full relative">
            <button
              onClick={() => {
                setShowSignupModal(false);
                setError(null);
              }}
              className="absolute top-4 right-4 text-2xl text-[var(--foreground-secondary)] hover:text-white"
            >
              ×
            </button>
            <h2 className="text-3xl font-bold text-white mb-6">Sign Up</h2>
            <form onSubmit={handleSignup} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-2 text-white">Name</label>
                <input
                  type="text"
                  value={signupData.name}
                  onChange={(e) => setSignupData({ ...signupData, name: e.target.value })}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-white transition-all text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2 text-white">Email</label>
                <input
                  type="email"
                  value={signupData.email}
                  onChange={(e) => setSignupData({ ...signupData, email: e.target.value })}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-white transition-all text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2 text-white">Password</label>
                <input
                  type="password"
                  value={signupData.password}
                  onChange={(e) => setSignupData({ ...signupData, password: e.target.value })}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-white transition-all text-white"
                  required
                  minLength={8}
                />
              </div>
              <div>
                <label className="block text-sm font-semibold mb-2 text-white">Confirm Password</label>
                <input
                  type="password"
                  value={signupData.confirmPassword}
                  onChange={(e) => setSignupData({ ...signupData, confirmPassword: e.target.value })}
                  className="w-full px-4 py-3 bg-[var(--background-secondary)] border-2 border-[var(--border-color)] rounded-xl focus:outline-none focus:border-white transition-all text-white"
                  required
                  minLength={8}
                />
              </div>
              {error && (
                <div className="p-4 bg-red-500/10 border border-red-500/50 rounded-xl text-red-400 text-sm">
                  {error}
                </div>
              )}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-white text-black rounded-xl font-bold hover:bg-gray-200 transition-all disabled:opacity-50"
              >
                {loading ? 'Creating account...' : 'Sign Up'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

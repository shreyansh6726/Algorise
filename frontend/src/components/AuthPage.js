import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  BadgeCheck,
  Eye,
  EyeOff,
  Fingerprint,
  KeyRound,
  Loader2,
  LogIn,
  Mail,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react';
import { API_BASE_URL } from '../config';

const loginDefaults = {
  name: '',
  userId: '',
  email: '',
  password: '',
};

const signupDefaults = {
  name: '',
  userId: '',
  email: '',
  password: '',
};

export default function AuthPage({ onAuthSuccess }) {
  const [mode, setMode] = useState('login');
  const [formData, setFormData] = useState(loginDefaults);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isSignup = mode === 'signup';

  useEffect(() => {
    setError('');
    setShowPassword(false);
    setFormData(isSignup ? { ...signupDefaults } : { ...loginDefaults });
  }, [mode, isSignup]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setFormData((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    const endpoint = isSignup ? 'signup' : 'login';
    const payload = isSignup
      ? {
          name: formData.name.trim(),
          user_id: formData.userId.trim(),
          email: formData.email.trim(),
          password: formData.password,
        }
      : {
          user_id: formData.userId.trim(),
          password: formData.password,
        };

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed.');
      }

      onAuthSuccess(data);
    } catch (submissionError) {
      setError(submissionError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page animate-fade-in">
      <div className="bg-glow-radial auth-glow-one"></div>
      <div className="bg-glow-radial auth-glow-two"></div>

      <div className="auth-shell">
        <section className="auth-hero glass-panel">
          <div className="auth-eyebrow">
            <ShieldCheck size={14} />
            Secure authenticated access
          </div>

          <h1 className="auth-title">Unlock Algorise prediction workflows.</h1>
          <p className="auth-copy">
            Sign up once, log in with your user ID, and move straight into company search,
            model training, and stock forecasting.
          </p>

          <div className="auth-highlights">
            <div className="auth-highlight-card">
              <Sparkles size={18} />
              <div>
                <strong>Personal workspace</strong>
                <span>One account, your own sessions.</span>
              </div>
            </div>
            <div className="auth-highlight-card">
              <BadgeCheck size={18} />
              <div>
                <strong>MongoDB-backed</strong>
                <span>Accounts are stored in your database.</span>
              </div>
            </div>
            <div className="auth-highlight-card">
              <Fingerprint size={18} />
              <div>
                <strong>Token protected</strong>
                <span>Dashboard calls require a valid session.</span>
              </div>
            </div>
          </div>
        </section>

        <section className="auth-card glass-panel">
          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${!isSignup ? 'active' : ''}`}
              onClick={() => setMode('login')}
            >
              <LogIn size={16} />
              Login
            </button>
            <button
              type="button"
              className={`auth-tab ${isSignup ? 'active' : ''}`}
              onClick={() => setMode('signup')}
            >
              <UserRound size={16} />
              Sign Up
            </button>
          </div>

          <div className="auth-card-header">
            <div className="auth-card-icon">
              {isSignup ? <UserRound size={22} /> : <KeyRound size={22} />}
            </div>
            <div>
              <h2>{isSignup ? 'Create your account' : 'Welcome back'}</h2>
              <p>
                {isSignup
                  ? 'Create a unique user ID and start forecasting.'
                  : 'Use your user ID and password to continue.'}
              </p>
            </div>
          </div>

          {error && <div className="auth-error">{error}</div>}

          <form className="auth-form" onSubmit={handleSubmit}>
            {isSignup && (
              <label className="auth-field">
                <span>Name</span>
                <div className="auth-input-wrap">
                  <UserRound size={16} className="auth-input-icon" />
                  <input
                    type="text"
                    name="name"
                    className="auth-input"
                    value={formData.name}
                    onChange={handleChange}
                    placeholder="Your full name"
                    autoComplete="name"
                    required
                  />
                </div>
              </label>
            )}

            <label className="auth-field">
              <span>User ID</span>
              <div className="auth-input-wrap">
                <Fingerprint size={16} className="auth-input-icon" />
                <input
                  type="text"
                  name="userId"
                  className="auth-input"
                  value={formData.userId}
                  onChange={handleChange}
                  placeholder="unique_user_id"
                  autoComplete={isSignup ? 'username' : 'username'}
                  required
                />
              </div>
              {isSignup && (
                <small className="auth-hint">Use letters, numbers, dots, dashes, or underscores.</small>
              )}
            </label>

            {isSignup && (
              <label className="auth-field">
                <span>Email</span>
                <div className="auth-input-wrap">
                  <Mail size={16} className="auth-input-icon" />
                  <input
                    type="email"
                    name="email"
                    className="auth-input"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="name@domain.com"
                    autoComplete="email"
                    required
                  />
                </div>
              </label>
            )}

            <label className="auth-field">
              <span>Password</span>
              <div className="auth-input-wrap">
                <KeyRound size={16} className="auth-input-icon" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  className="auth-input auth-password-input"
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="At least 8 characters"
                  autoComplete={isSignup ? 'new-password' : 'current-password'}
                  required
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((current) => !current)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>

            <button type="submit" className="auth-submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 size={18} className="spinner auth-button-spinner" />
                  {isSignup ? 'Creating account...' : 'Signing in...'}
                </>
              ) : (
                <>
                  {isSignup ? 'Create account' : 'Sign in'}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          <p className="auth-switch-copy">
            {isSignup ? 'Already have an account?' : 'Need an account?'}{' '}
            <button
              type="button"
              className="auth-switch-button"
              onClick={() => setMode(isSignup ? 'login' : 'signup')}
            >
              {isSignup ? 'Switch to login' : 'Create one now'}
            </button>
          </p>
        </section>
      </div>
    </div>
  );
}
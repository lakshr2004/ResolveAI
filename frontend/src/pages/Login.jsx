
import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import {
  ShieldCheck,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  Loader2,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();

  const { login, loading } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password) {
      setError('Please enter your email and password.');
      return;
    }

    try {
      await login(email.trim(), password);

      const destination =
        location.state?.from?.pathname || '/';

      navigate(destination, { replace: true });

    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;

      if (status === 401) {
        setError('Invalid email or password.');

      } else if (status === 403) {
        setError(
          'Your account is inactive. Contact an administrator.'
        );

      } else if (!err.response) {
        setError(
          'Unable to connect to the server. Please try again.'
        );

      } else if (Array.isArray(detail)) {
        setError(
          detail
            .map((item) => item.msg || 'Invalid input')
            .join(', ')
        );

      } else if (typeof detail === 'string') {
        setError(detail);

      } else {
        setError('Login failed. Please try again.');
      }
    }
  };

  return (
    <main className="login-page">

      <div className="login-glow login-glow-one" />
      <div className="login-glow login-glow-two" />

      <section className="login-container">

        {/* BRAND */}
        <div className="login-brand">

          <div className="login-brand-icon">
            <ShieldCheck size={25} />
          </div>

          <div>
            <h1>
              Resolve<span>AI</span>
            </h1>

            <p>SUPPORT INTELLIGENCE PLATFORM</p>
          </div>

        </div>

        {/* LOGIN CARD */}
        <div className="login-card">

          <div className="login-heading">

            <span className="login-eyebrow">
              SECURE WORKSPACE
            </span>

            <h2>Welcome back</h2>

            <p>
              Sign in to access your support operations dashboard.
            </p>

          </div>

          {/* ERROR MESSAGE */}
          {error && (
            <div className="login-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>

            {/* EMAIL */}
            <div className="login-field">

              <label htmlFor="email">
                Email address
              </label>

              <div className="login-input-wrap">

                <Mail size={17} />

                <input
                  id="email"
                  type="text"
                  placeholder="admin@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  required
                />

              </div>

            </div>

            {/* PASSWORD */}
            <div className="login-field">

              <label htmlFor="password">
                Password
              </label>

              <div className="login-input-wrap">

                <Lock size={17} />

                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />

                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={
                    showPassword ? 'Hide password' : 'Show password'
                  }
                >
                  {showPassword ? (
                    <EyeOff size={17} />
                  ) : (
                    <Eye size={17} />
                  )}
                </button>

              </div>

            </div>

            {/* SUBMIT */}
            <button
              type="submit"
              className="login-submit"
              disabled={loading}
            >

              {loading ? (
                <>
                  <Loader2
                    size={17}
                    className="login-spinner"
                  />
                  Signing in...
                </>
              ) : (
                <>
                  Sign in to workspace
                  <ArrowRight size={17} />
                </>
              )}

            </button>

          </form>

          {/* SECURITY FOOTER */}
          <div className="login-security">
            <ShieldCheck size={15} />
            <span>
              Protected by secure authentication
            </span>
          </div>

        </div>

        {/* PAGE FOOTER */}
        <p className="login-footer">
          ResolveAI · AI-Powered Support Ticket Resolution
        </p>

      </section>

    </main>
  );
}

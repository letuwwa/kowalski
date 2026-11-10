import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useLocation } from 'react-router';
import { signInError } from './authApi';
import { useAuth } from './authContext';
import { getReturnPath } from './returnPath';

export function LoginPage() {
  const { user, signIn, notice } = useAuth();
  const location = useLocation();
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    const identifier = String(fields.get('identifier') ?? '').trim();
    if (!identifier) {
      setError('Enter your email or username.');
      return;
    }
    setError('');
    setPending(true);
    try {
      await signIn(identifier, String(fields.get('password') ?? ''));
    } catch (error) {
      setError(signInError(error));
    } finally {
      setPending(false);
    }
  }

  if (user) return <Navigate to={getReturnPath(location.state?.from)} replace />;

  return (
    <section aria-labelledby="login-title">
      <h1 id="login-title">Sign in</h1>
      <form onSubmit={handleLogin}>
        <div className="field">
          <label htmlFor="identifier">Email or username</label>
          <input
            id="identifier"
            name="identifier"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={255}
            disabled={pending}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <div className="password-field">
            <input
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              autoComplete="current-password"
              disabled={pending}
              required
            />
            <button
              type="button"
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              onClick={() => setShowPassword(!showPassword)}
              disabled={pending}
            >
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        <button type="submit" disabled={pending}>
          {pending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </section>
  );
}

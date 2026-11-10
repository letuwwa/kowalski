import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useLocation } from 'react-router';
import { registrationError } from './authApi';
import type { Registration, RegistrationFeedback } from './authApi';
import { useAuth } from './authContext';
import { getReturnPath } from './returnPath';

const fields = [
  { name: 'first_name', label: 'First name', type: 'text', autoComplete: 'given-name' },
  { name: 'last_name', label: 'Last name', type: 'text', autoComplete: 'family-name' },
  { name: 'email', label: 'Email', type: 'email', autoComplete: 'email' },
  { name: 'username', label: 'Username', type: 'text', autoComplete: 'username' },
  { name: 'password', label: 'Password', type: 'password', autoComplete: 'new-password' },
] as const;

export function RegisterPage() {
  const { user, register } = useAuth();
  const location = useLocation();
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<RegistrationFeedback | null>(null);

  async function handleRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const data: Registration = {
      first_name: String(form.get('first_name') ?? '').trim(),
      last_name: String(form.get('last_name') ?? '').trim(),
      email: String(form.get('email') ?? '').trim(),
      username: String(form.get('username') ?? '').trim(),
      password: String(form.get('password') ?? ''),
    };
    setFeedback(null);
    setPending(true);
    try {
      await register(data);
    } catch (error) {
      setFeedback(registrationError(error));
    } finally {
      setPending(false);
    }
  }

  if (user) return <Navigate to={getReturnPath(location.state?.from)} replace />;

  return (
    <section aria-labelledby="register-title">
      <h1 id="register-title">Create an account</h1>
      <form onSubmit={handleRegister}>
        {feedback && <p className="error" role="alert">{feedback.message}</p>}
        {fields.map(({ name, label, type, autoComplete }) => {
          const error = feedback?.fields?.[name];
          return (
            <div className="field" key={name}>
              <label htmlFor={name}>{label}</label>
              <input
                id={name}
                name={name}
                type={type}
                autoComplete={autoComplete}
                autoCapitalize={name === 'email' || name === 'username' ? 'none' : undefined}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? `${name}-error` : name === 'password' ? 'password-hint' : undefined}
                disabled={pending}
                required
              />
              {error && <p className="error" id={`${name}-error`}>{error}</p>}
              {name === 'password' && <small id="password-hint">Use 12–128 characters.</small>}
            </div>
          );
        })}
        <button type="submit" disabled={pending}>
          {pending ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="auth-switch">
        Already have an account? <Link to="/login" state={location.state}>Sign in</Link>
      </p>
    </section>
  );
}

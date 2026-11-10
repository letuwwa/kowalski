import { useState } from 'react';
import { useAuth } from '../auth/authContext';

export function AccountPage() {
  const { user, signOut } = useAuth();
  const [pending, setPending] = useState(false);

  if (!user) return null;

  async function handleLogout() {
    if (pending) return;
    setPending(true);
    try {
      await signOut();
    } finally {
      setPending(false);
    }
  }

  return (
    <section aria-labelledby="workspace-title">
      <h1 id="workspace-title">Account</h1>
      <dl className="account">
        <div><dt>Username</dt><dd>{user.username}</dd></div>
        <div><dt>Email</dt><dd>{user.email}</dd></div>
      </dl>
      <button type="button" disabled={pending} onClick={handleLogout}>
        {pending ? 'Signing out…' : 'Sign out'}
      </button>
    </section>
  );
}

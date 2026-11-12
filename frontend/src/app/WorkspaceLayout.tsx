import { useState } from 'react';
import { NavLink, Outlet } from 'react-router';
import { useAuth } from '../features/auth/authContext';

export function WorkspaceLayout() {
  const { signOut } = useAuth();
  const [pending, setPending] = useState(false);

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
    <>
      <nav className="workspace-nav" aria-label="Main navigation">
        <div className="nav-links"><NavLink to="/scans">Scan</NavLink><NavLink to="/profile">Profile</NavLink></div>
        <button type="button" disabled={pending} onClick={handleLogout}>
          {pending ? 'Signing out…' : 'Sign out'}
        </button>
      </nav>
      <main className="workspace-page"><Outlet /></main>
    </>
  );
}

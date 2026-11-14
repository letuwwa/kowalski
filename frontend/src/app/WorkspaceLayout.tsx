import { useState } from 'react';
import { NavLink, Outlet } from 'react-router';
import { useAuth } from '../features/auth/authContext';

export function WorkspaceLayout() {
  const { user, signOut } = useAuth();
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
        <div className="nav-links">
          <NavLink to="/dashboard">Overview</NavLink>
          <NavLink to="/scans">Scans</NavLink>
          <NavLink to="/history">Target history</NavLink>
          <NavLink to="/profile">Profile</NavLink>
        </div>
        <div className="nav-account">
          <span>{user?.username}</span>
          <button type="button" disabled={pending} onClick={handleLogout}>
            {pending ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </nav>
      <main className="workspace-page">
        <Outlet />
      </main>
    </>
  );
}

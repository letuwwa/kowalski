import { useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { registerAccount, signIn, signOut } from './authApi';
import type { Registration, Session } from './authApi';
import { AuthContext } from './authContext';
import { createAuthenticatedRequest } from './authenticatedRequest';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState('');
  const sessionRef = useRef<Session | null>(null);

  function updateSession(next: Session | null) {
    sessionRef.current = next;
    setSession(next);
  }

  const [request] = useState(() => createAuthenticatedRequest(
    () => sessionRef.current,
    updateSession,
    () => {
      updateSession(null);
      setNotice('Your session has expired. Sign in again.');
    },
  ));

  async function login(identifier: string, password: string) {
    setNotice('');
    updateSession(await signIn(identifier, password));
  }

  async function register(fields: Registration) {
    setNotice('');
    updateSession(await registerAccount(fields));
  }

  async function logout() {
    const current = sessionRef.current;
    if (!current) return;
    updateSession(null);
    setNotice('Signing out…');
    try {
      await signOut(current.tokens.refresh_token);
      if (!sessionRef.current) setNotice('You’ve signed out.');
    } catch {
      if (!sessionRef.current) setNotice('You’ve signed out in this tab. The server did not confirm sign-out.');
    }
  }

  return (
    <AuthContext.Provider value={{
      user: session?.user ?? null,
      accessToken: session?.tokens.access_token ?? null,
      notice,
      signIn: login,
      register,
      signOut: logout,
      request,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

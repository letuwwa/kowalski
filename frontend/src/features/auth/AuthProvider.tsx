import { useState } from 'react';
import type { ReactNode } from 'react';
import { registerAccount, signIn, signOut } from './authApi';
import type { Registration, Session } from './authApi';
import { AuthContext } from './authContext';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [notice, setNotice] = useState('');

  async function login(identifier: string, password: string) {
    setNotice('');
    setSession(await signIn(identifier, password));
  }

  async function register(fields: Registration) {
    setNotice('');
    setSession(await registerAccount(fields));
  }

  async function logout() {
    if (!session) return;
    try {
      await signOut(session.tokens.refresh_token);
      setNotice('You’ve signed out.');
    } catch {
      setNotice('You’ve signed out in this tab. The server did not confirm sign-out.');
    } finally {
      setSession(null);
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
    }}>
      {children}
    </AuthContext.Provider>
  );
}

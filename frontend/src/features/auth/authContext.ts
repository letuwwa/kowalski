import { createContext, useContext } from 'react';
import type { Registration, User } from './authApi';

type AuthState = {
  user: User | null;
  accessToken: string | null;
  notice: string;
  signIn: (identifier: string, password: string) => Promise<void>;
  register: (fields: Registration) => Promise<void>;
  signOut: () => Promise<void>;
};

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error('useAuth must be used inside AuthProvider');
  return auth;
}

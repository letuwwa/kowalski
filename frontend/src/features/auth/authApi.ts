import { ApiError, requestJson } from '../../shared/api/client.ts';

export type User = {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
};

type TokenPair = { access_token: string; refresh_token: string };
export type Session = { user: User; tokens: TokenPair };

export async function signIn(identifier: string, password: string): Promise<Session> {
  const { tokens } = await requestJson<{ tokens: TokenPair }>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier: identifier.trim(), password }),
  });

  const { user } = await requestJson<{ user: User }>('/auth/me', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });
  return { user, tokens };
}

export async function signOut(refreshToken: string): Promise<void> {
  // The refresh token can revoke this login even after its access token expires.
  await requestJson('/auth/logout', {
    method: 'POST',
    headers: { Authorization: `Bearer ${refreshToken}` },
  });
}

export function signInError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401 && error.message === 'Invalid credentials') {
      return 'Check your email or username and password, then try again.';
    }
    if (error.status === 401 || error.status === 422) {
      return 'Kowalski couldn’t verify this session. Sign in again.';
    }
    if (error.status === 403) return 'This account does not have access.';
    if (error.status === 429) return 'Too many attempts. Wait a minute and try again.';
  }
  return 'Kowalski couldn’t reach the sign-in service. Try again in a moment.';
}

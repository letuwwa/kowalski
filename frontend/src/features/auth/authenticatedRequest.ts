import { ApiError, requestJson } from '../../shared/api/client.ts';
import type { Session } from './authApi.ts';

export type AuthenticatedRequest = <T>(path: `/${string}`, options?: RequestInit) => Promise<T>;

export class SessionExpiredError extends Error {
  constructor() { super('Your session has expired. Sign in again.'); }
}

// One refresh per session, even when several protected requests expire together.
export function createAuthenticatedRequest(
  getSession: () => Session | null,
  setSession: (session: Session) => void,
  expireSession: () => void,
): AuthenticatedRequest {
  let refreshing: { token: string; promise: Promise<Session> } | null = null;

  function currentSession(refreshToken: string): Session {
    const current = getSession();
    if (!current || current.tokens.refresh_token !== refreshToken) throw new SessionExpiredError();
    return current;
  }

  function expire(refreshToken: string) {
    if (getSession()?.tokens.refresh_token === refreshToken) expireSession();
  }

  async function refresh(session: Session): Promise<Session> {
    const refreshToken = session.tokens.refresh_token;
    try {
      const { access_token } = await requestJson<{ access_token: string }>('/auth/refresh', {
        method: 'POST', headers: { Authorization: `Bearer ${refreshToken}` },
      });
      if (!access_token) throw new Error('The refresh response did not contain an access token.');
      const current = currentSession(refreshToken);
      const next = { ...current, tokens: { ...current.tokens, access_token } };
      setSession(next);
      return next;
    } catch (error) {
      if (error instanceof ApiError && [401, 403, 422].includes(error.status)) {
        expire(refreshToken);
        throw new SessionExpiredError();
      }
      throw error;
    }
  }

  return async function authenticatedRequest<T>(path: `/${string}`, options: RequestInit = {}): Promise<T> {
    const initial = getSession();
    if (!initial) throw new SessionExpiredError();
    const refreshToken = initial.tokens.refresh_token;
    const send = (accessToken: string) => {
      const headers = new Headers(options.headers);
      headers.set('Authorization', `Bearer ${accessToken}`);
      return requestJson<T>(path, { ...options, headers });
    };
    try {
      const result = await send(initial.tokens.access_token);
      currentSession(refreshToken);
      return result;
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
    }

    let current = currentSession(refreshToken);
    if (current.tokens.access_token === initial.tokens.access_token) {
      if (!refreshing || refreshing.token !== refreshToken) {
        const pending = { token: refreshToken, promise: refresh(current) };
        refreshing = pending;
        void pending.promise.finally(() => {
          if (refreshing === pending) refreshing = null;
        }).catch(() => {});
      }
      current = await refreshing.promise;
    }
    currentSession(refreshToken);
    // Only an explicit 401 retries once. Never retry a timeout or lost POST response.
    try {
      const result = await send(current.tokens.access_token);
      currentSession(refreshToken);
      return result;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        expire(refreshToken);
        throw new SessionExpiredError();
      }
      throw error;
    }
  };
}

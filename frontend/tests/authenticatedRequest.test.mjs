import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createAuthenticatedRequest, SessionExpiredError } from '../src/features/auth/authenticatedRequest.ts';

function client() {
  let session = { user: { id: 'test-user' }, tokens: { access_token: 'expired', refresh_token: 'refresh' } };
  let updates = 0;
  const request = createAuthenticatedRequest(() => session, (next) => { session = next; updates++; }, () => { session = null; });
  return { request, session: () => session, logout: () => { session = null; }, updates: () => updates };
}
const expired = () => Response.json({ msg: 'Token has expired' }, { status: 401 });

test('concurrent expired requests share one JWT refresh', async (t) => {
  const auth = client();
  let refreshCalls = 0;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    const token = new Headers(options.headers).get('Authorization');
    if (url === '/api/auth/refresh') {
      refreshCalls++;
      assert.equal(token, 'Bearer refresh');
      return Response.json({ access_token: 'renewed' });
    }
    return token === 'Bearer expired' ? expired() : Response.json({ ok: true });
  });
  const results = await Promise.all([auth.request('/scans'), auth.request('/scans/test')]);
  assert.deepEqual(results, [{ ok: true }, { ok: true }]);
  assert.equal(refreshCalls, 1);
  assert.equal(auth.session().tokens.access_token, 'renewed');
});

test('an expired POST retries once after explicit JWT rejection, with the same payload', async (t) => {
  const auth = client();
  let creates = 0;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url === '/api/auth/refresh') return Response.json({ access_token: 'renewed' });
    assert.equal(options.method, 'POST');
    assert.equal(options.body, '{"target":"127.0.0.1"}');
    if (new Headers(options.headers).get('Authorization') === 'Bearer expired') return expired();
    creates++;
    return Response.json({ id: 'job-id' }, { status: 202 });
  });
  assert.deepEqual(await auth.request('/scans', { method: 'POST', body: '{"target":"127.0.0.1"}' }), { id: 'job-id' });
  assert.equal(creates, 1);
});

test('a lost POST response is never retried automatically', async (t) => {
  const auth = client();
  const fetch = t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network disconnected'); });
  await assert.rejects(auth.request('/scans', { method: 'POST' }), /Network disconnected/);
  assert.equal(fetch.mock.callCount(), 1);
});

test('failed refresh signs out and stops retrying', async (t) => {
  const auth = client();
  const fetch = t.mock.method(globalThis, 'fetch', async () => expired());
  await assert.rejects(auth.request('/scans'), SessionExpiredError);
  assert.equal(auth.session(), null);
  assert.equal(fetch.mock.callCount(), 2);
});

test('sign-out during a refresh cannot restore the old session', async (t) => {
  const auth = client();
  let complete;
  let started;
  const refreshStarted = new Promise((resolve) => { started = resolve; });
  t.mock.method(globalThis, 'fetch', async (url) => {
    if (url !== '/api/auth/refresh') return expired();
    started();
    return new Promise((resolve) => { complete = resolve; });
  });
  const pending = auth.request('/scans');
  await refreshStarted;
  auth.logout();
  complete(Response.json({ access_token: 'renewed' }));
  await assert.rejects(pending, SessionExpiredError);
  assert.equal(auth.session(), null);
  assert.equal(auth.updates(), 0);
});

test('a repeated 401 after refresh ends the session instead of looping', async (t) => {
  const auth = client();
  const fetch = t.mock.method(globalThis, 'fetch', async (url) => url === '/api/auth/refresh'
    ? Response.json({ access_token: 'renewed' }) : expired());
  await assert.rejects(auth.request('/scans'), SessionExpiredError);
  assert.equal(auth.session(), null);
  assert.equal(fetch.mock.callCount(), 3);
});

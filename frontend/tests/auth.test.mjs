import assert from 'node:assert/strict';
import { test } from 'node:test';
import { signIn, signInError, signOut } from '../src/features/auth/authApi.ts';

test('sign-in authenticates the profile and sign-out revokes the session', async (t) => {
  const tokens = { access_token: 'test-access', refresh_token: 'test-refresh' };
  const user = { id: 'test-id', username: 'test-user' };
  const fetch = t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (url === '/api/auth/login') {
      assert.equal(options.method, 'POST');
      assert.deepEqual(JSON.parse(options.body), { identifier: 'test-user', password: ' keep spaces ' });
      return Response.json({ tokens });
    }
    if (url === '/api/auth/me') {
      assert.equal(options.headers.Authorization, `Bearer ${tokens.access_token}`);
      return Response.json({ user });
    }
    assert.equal(url, '/api/auth/logout');
    assert.equal(options.method, 'POST');
    assert.equal(options.headers.Authorization, `Bearer ${tokens.refresh_token}`);
    return Response.json({ message: 'Token revoked' });
  });

  const session = await signIn(' test-user ', ' keep spaces ');
  assert.deepEqual(session.user, user);
  await signOut(session.tokens.refresh_token);
  assert.equal(fetch.mock.callCount(), 3);
});

test('bad credentials stop sign-in before the protected profile request', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () =>
    Response.json({ message: 'Invalid credentials' }, { status: 401 }),
  );

  await assert.rejects(signIn('test-user', 'bad-password'), (error) => {
    assert.match(signInError(error), /Check your email or username and password/);
    return true;
  });
  assert.equal(fetch.mock.callCount(), 1);
});

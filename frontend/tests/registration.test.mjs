import assert from 'node:assert/strict';
import { test } from 'node:test';
import { registerAccount, registrationError } from '../src/features/auth/authApi.ts';

const registration = {
  first_name: 'Local',
  last_name: 'Tester',
  email: 'local@example.test',
  username: 'local_tester',
  password: ' password with spaces ',
};

test('registration uses the session issued by Flask', async (t) => {
  const { password, ...user } = registration;
  const tokens = { access_token: 'test-access', refresh_token: 'test-refresh' };
  const fetch = t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/auth/register');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), registration);
    return Response.json({ user, tokens }, { status: 201 });
  });

  assert.deepEqual(await registerAccount(registration), { user, tokens });
  assert.equal(fetch.mock.callCount(), 1);
});

test('registration shows validation messages for known fields', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({
    errors: { username: 'Choose a valid username', email: 42, unknown: 'Ignore me' },
  }, { status: 400 }));

  await assert.rejects(registerAccount(registration), (error) => {
    assert.deepEqual(registrationError(error).fields, { username: 'Choose a valid username' });
    return true;
  });
});

test('registration explains a duplicate account or rate limit', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({}, { status: 409 }));
  await assert.rejects(registerAccount(registration), (error) => {
    assert.match(registrationError(error).message, /already registered/);
    return true;
  });
  fetch.mock.mockImplementation(async () => Response.json({}, { status: 429 }));
  await assert.rejects(registerAccount(registration), (error) => {
    assert.match(registrationError(error).message, /Too many registration attempts/);
    return true;
  });
});

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getReturnPath } from '../src/features/auth/returnPath.ts';

test('return to the requested page with its query and fragment after login', () => {
  assert.equal(getReturnPath('/profile?tab=details#email'), '/profile?tab=details#email');
});

test('reject external, malformed, and authentication return destinations', () => {
  for (const path of [
    undefined,
    'https://example.test/account',
    '//example.test',
    '/\\example.test',
    '/account/..//example.test',
    '/login?next=/account',
    '/LOGIN/',
    '/register?next=/profile',
  ]) {
    assert.equal(getReturnPath(path), '/profile');
  }
});

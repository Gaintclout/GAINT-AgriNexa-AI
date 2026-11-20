import test from 'node:test';
import assert from 'node:assert/strict';
import { authorizationMessage, authorizedFetch, withBearer } from '../src/authUtils.js';
import { loginOperator } from '../src/gisApi.js';

test('Bearer header is added without discarding existing headers', () => {
  const options = withBearer({ headers: { 'Content-Type': 'application/json' } }, 'test-token');
  assert.equal(options.headers.get('Authorization'), 'Bearer test-token');
  assert.equal(options.headers.get('Content-Type'), 'application/json');
});

test('401 invokes session invalidation but 403 does not', async () => {
  let invalidations = 0;
  const fetch401 = async () => ({ status: 401 });
  const fetch403 = async () => ({ status: 403 });
  await authorizedFetch('/protected', {}, 'token', () => invalidations++, fetch401);
  await authorizedFetch('/protected', {}, 'token', () => invalidations++, fetch403);
  assert.equal(invalidations, 1);
  assert.match(authorizationMessage(401), /expired/);
  assert.match(authorizationMessage(403), /not authorized/);
});

test('credentials are not added when token is absent', () => {
  assert.equal(withBearer({}, '').headers.has('Authorization'), false);
});

test('login sends the expected request to the configured authentication endpoint', async () => {
  let request;
  const fetchImpl = async (...args) => {
    request = args;
    return { ok: true, json: async () => ({ access_token: 'synthetic-token' }) };
  };
  await loginOperator('synthetic@example.test', 'synthetic-only-password', undefined, fetchImpl);
  assert.equal(request[0], '/api/v1/auth/login');
  assert.equal(request[1].method, 'POST');
  assert.equal(request[1].headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(request[1].body), {
    email: 'synthetic@example.test',
    password: 'synthetic-only-password',
  });
});

test('login presents status-specific sanitized messages for HTTP failures', async () => {
  const messages = new Map([
    [401, 'Incorrect email or password.'],
    [403, 'This account is not authorized to sign in (HTTP 403).'],
    [404, 'The authentication endpoint was not found (HTTP 404).'],
    [500, 'Authentication service error (HTTP 500). Please try again later.'],
    [503, 'Authentication service unavailable (HTTP 503). This is a server configuration or availability issue, not an invalid-password response.'],
  ]);
  for (const [status, message] of messages) {
    const fetchImpl = async () => ({ ok: false, status });
    await assert.rejects(
      loginOperator('synthetic@example.test', 'synthetic-only-password', undefined, fetchImpl),
      { message },
    );
  }
});

test('login normalizes network failures without exposing low-level details', async () => {
  const fetchImpl = async () => { throw new TypeError('synthetic connection detail'); };
  await assert.rejects(
    loginOperator('synthetic@example.test', 'synthetic-only-password', undefined, fetchImpl),
    { message: 'Cannot reach the authentication service. Check the API connection.' },
  );
});

test('login preserves request cancellation', async () => {
  const fetchImpl = async () => {
    const error = new Error('Request aborted');
    error.name = 'AbortError';
    throw error;
  };
  await assert.rejects(
    loginOperator('synthetic@example.test', 'synthetic-only-password', undefined, fetchImpl),
    { name: 'AbortError' },
  );
});

test('login rejects malformed and tokenless success responses safely', async () => {
  const invalidJson = async () => ({ ok: true, json: async () => { throw new SyntaxError('synthetic parse detail'); } });
  const missingToken = async () => ({ ok: true, json: async () => ({}) });
  await assert.rejects(
    loginOperator('synthetic@example.test', 'synthetic-only-password', undefined, invalidJson),
    { message: 'Authentication service returned an invalid response.' },
  );
  await assert.rejects(
    loginOperator('synthetic@example.test', 'synthetic-only-password', undefined, missingToken),
    { message: 'Authentication service returned an invalid sign-in response.' },
  );
});

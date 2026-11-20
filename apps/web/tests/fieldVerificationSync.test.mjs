import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(
  new URL('../src/fieldVerificationSync.js', import.meta.url),
  'utf8'
);

const { offlineDatabaseName, validateEvidence, syncEvidenceQueue } = await import(
  'data:text/javascript;base64,' +
  Buffer.from(source).toString('base64')
);

test('offline databases are isolated by authenticated subject', () => {
  assert.notEqual(offlineDatabaseName('drafts', 'verifier-a'), offlineDatabaseName('drafts', 'verifier-b'));
  assert.throws(() => offlineDatabaseName('drafts', ''), /Authenticated user/);
});

const valid = () => ({
  client_record_id: 'field_123',
  parcel_id: '123e4567-e89b-42d3-a456-426614174000',
  observation: 'Healthy crop observed',
  latitude: 17.4,
  longitude: 78.5,
  captured_at: '2025-01-01T00:00:00.000Z'
});

test('valid observation uses only allowed fields', () => {
  const result = validateEvidence({
    ...valid(),
    unexpected: 'discard'
  });
  assert.equal(result.observation, 'Healthy crop observed');
  assert.equal('unexpected' in result, false);
});

test('rejects missing client record identifier', () => {
  assert.throws(
    () => validateEvidence({ ...valid(), client_record_id: '' }),
    /client record ID/
  );
});

test('rejects invalid GPS coordinates', () => {
  assert.throws(
    () => validateEvidence({ ...valid(), latitude: 91 }),
    /GPS/
  );
  assert.throws(
    () => validateEvidence({ ...valid(), longitude: -181 }),
    /GPS/
  );
});

test('rejects empty or oversized observations', () => {
  assert.throws(
    () => validateEvidence({ ...valid(), observation: '  ' }),
    /Observation/
  );
  assert.throws(
    () => validateEvidence({
      ...valid(),
      observation: 'x'.repeat(4001)
    }),
    /Observation/
  );
});

test('rejects future capture timestamps', () => {
  assert.throws(
    () => validateEvidence({
      ...valid(),
      captured_at: '2999-01-01T00:00:00Z'
    }),
    /timestamp/
  );
});

test('requires authentication before synchronization', async () => {
  await assert.rejects(
    syncEvidenceQueue({ token: '' }),
    /Authentication required/
  );
});

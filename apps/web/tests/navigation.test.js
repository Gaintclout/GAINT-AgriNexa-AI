import test from 'node:test';
import assert from 'node:assert/strict';
import { navigationForRole } from '../src/navigation.js';
import { normalizeAgentIds } from '../src/agentCatalog.js';

const idsFor = role => navigationForRole(role).map(item => item.id);

test('anonymous visitors only see the public dashboard', () => {
  assert.deepEqual(idsFor(null), ['overview']);
});

test('role navigation keeps farmer, verifier, and officer workspaces separate', () => {
  assert.deepEqual(idsFor('farmer'), ['overview', 'parcels']);
  assert.ok(idsFor('field_verifier').includes('verification'));
  assert.ok(!idsFor('field_verifier').includes('review'));
  assert.ok(idsFor('officer').includes('review'));
  assert.ok(!idsFor('officer').includes('verification'));
});

test('privileged roles see only the modules authorized for their backend role', () => {
  assert.ok(idsFor('admin').includes('review'));
  assert.ok(idsFor('gis_operator').includes('scim'));
  assert.ok(idsFor('ml_team').includes('agents'));
  assert.ok(!idsFor('gis_operator').includes('review'));
});

test('agent display uses only unique valid identifiers supplied by API metadata', () => {
  const ids = normalizeAgentIds(['INTAKE', 'PROFILE', 'WEATHER', 'CROP_ADVISORY', 'MARKET', 'SCHEME', 'ESCALATION', 'LEARNING', 'LEARNING', 'new-agent', null]);
  assert.deepEqual(ids, ['INTAKE', 'PROFILE', 'WEATHER', 'CROP_ADVISORY', 'MARKET', 'SCHEME', 'ESCALATION', 'LEARNING']);
  assert.equal(new Set(ids).size, 8);
  assert.deepEqual(normalizeAgentIds(null), []);
});

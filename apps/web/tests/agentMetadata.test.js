import test from 'node:test';
import assert from 'node:assert/strict';
import { loadAgentMetadata } from '../src/agentApi.js';
import { AGENT_DEFINITIONS, normalizeAgentRecords, summarizeAgentRecords } from '../src/agentCatalog.js';

const IDS = ['INTAKE', 'PROFILE', 'WEATHER', 'CROP_ADVISORY', 'MARKET', 'SCHEME', 'ESCALATION', 'LEARNING'];
const records = IDS.map(id => ({ id, status: 'disabled', execution_enabled: false, learning_enabled: false }));

test('loads agent metadata through the authenticated request mechanism', async () => {
  let called;
  const result = await loadAgentMetadata(async (path, options) => {
    called = { path, options };
    return { ok: true, json: async () => records };
  }, 'signal');
  assert.equal(called.path, '/api/v1/agents');
  assert.equal(called.options.method, 'GET');
  assert.equal(called.options.signal, 'signal');
  assert.equal(result.length, 8);
});

test('preserves API status and capability flags for all eight agents', () => {
  records[0] = { ...records[0], status: 'enabled', execution_enabled: true };
  const agents = normalizeAgentRecords(records, 'admin');
  assert.deepEqual(agents.map(agent => agent.id), IDS);
  assert.equal(agents[0].status, 'enabled');
  assert.equal(agents[0].executionEnabled, true);
  assert.equal(agents[0].learningEnabled, false);
  assert.equal(agents[0].genericExecutionAvailable, false);
  assert.equal(agents[2].routeRegistered, true);
  assert.equal(agents[2].roleAuthorized, true);
  assert.equal(agents[2].runtimeReadiness, 'not_verified');
});

test('keeps dedicated workflow availability separate from registry execution', () => {
  const [weather] = normalizeAgentRecords([records[2]], 'gis_operator');
  assert.equal(weather.executionEnabled, false);
  assert.equal(weather.routeRegistered, true);
  assert.equal(weather.roleAuthorized, true);
  assert.equal(weather.endpoint, AGENT_DEFINITIONS.WEATHER.endpoint);
});

test('marks role-restricted learning workflow unavailable to GIS operators', () => {
  const [learning] = normalizeAgentRecords([records[7]], 'gis_operator');
  assert.equal(learning.routeRegistered, true);
  assert.equal(learning.roleAuthorized, false);
  assert.equal(learning.learningEnabled, false);
});

test('summarizes registry status and dedicated route registration', () => {
  const agents = normalizeAgentRecords(records, 'admin');
  assert.deepEqual(summarizeAgentRecords(agents), {
    total: 8,
    enabled: 1,
    disabled: 7,
    routes: 8
  });
});

test('surfaces authorization failures from the authenticated request', async () => {
  for (const status of [401, 403]) {
    const error = Object.assign(new Error(`authorization ${status}`), { status });
    await assert.rejects(() => loadAgentMetadata(async () => { throw error; }), candidate => candidate.status === status);
  }
});

test('rejects unsuccessful and malformed API responses', async () => {
  await assert.rejects(() => loadAgentMetadata(async () => ({ ok: false, status: 503 })), /HTTP 503/);
  await assert.rejects(() => loadAgentMetadata(async () => ({ ok: true, json: async () => ({}) })), /invalid/);
});

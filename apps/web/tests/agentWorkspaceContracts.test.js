import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const workspaces = [
  ['AgentIntakeWorkspace.jsx', '/api/v1/agents/intake-profile/availability', '/api/v1/agents/intake-profile/preview'],
  ['AgentWeatherWorkspace.jsx', '/api/v1/agents/weather/forecast'],
  ['AgentCropAdvisoryWorkspace.jsx', '/api/v1/agents/crop-advisory/generate'],
  ['AgentMarketWorkspace.jsx', '/api/v1/agents/market/prices'],
  ['AgentSchemeWorkspace.jsx', '/api/v1/agents/schemes/screen'],
  ['AgentEscalationWorkspace.jsx', '/api/v1/agents/escalation/screen'],
  ['AgentLearningWorkspace.jsx', '/api/v1/agents/learning/review'],
];

test('every implemented agent workspace uses authenticated request and its registered route', async () => {
  for (const [filename, ...routes] of workspaces) {
    const source = await readFile(new URL(`../src/${filename}`, import.meta.url), 'utf8');
    assert.match(source, /useAuth/);
    assert.match(source, /\brequest\s*\(/);
    for (const route of routes) assert.ok(source.includes(route), `${filename} must call ${route}`);
  }
});

test('frontend keeps GIS operators out of the learning workflow', async () => {
  const source = await readFile(new URL('../src/AgentGovernance.jsx', import.meta.url), 'utf8');
  assert.match(source, /role\s*!==\s*['"]gis_operator['"]\s*&&\s*<AgentLearningWorkspace/);
});

test('frontend does not call the disabled generic execution route', async () => {
  for (const [filename] of workspaces) {
    const source = await readFile(new URL(`../src/${filename}`, import.meta.url), 'utf8');
    assert.doesNotMatch(source, /\/api\/v1\/agents\/[^'"`]+\/execute/);
  }
});

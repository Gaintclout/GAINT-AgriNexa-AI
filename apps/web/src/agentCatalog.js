const IDENTIFIER = /^[A-Z][A-Z0-9_]{0,63}$/;

export const AGENT_DEFINITIONS = Object.freeze({
  INTAKE: { name: 'Intake', workflow: 'Audited intake/profile preview', endpoint: 'POST /api/v1/agents/intake-profile/preview', roles: ['admin', 'gis_operator', 'ml_team'] },
  PROFILE: { name: 'Profile', workflow: 'Audited intake/profile preview', endpoint: 'POST /api/v1/agents/intake-profile/preview', roles: ['admin', 'gis_operator', 'ml_team'] },
  WEATHER: { name: 'Weather', workflow: 'Weather forecast', endpoint: 'POST /api/v1/agents/weather/forecast', roles: ['admin', 'gis_operator', 'ml_team'] },
  CROP_ADVISORY: { name: 'Crop Advisory', workflow: 'Crop advisory generation', endpoint: 'POST /api/v1/agents/crop-advisory/generate', roles: ['admin', 'gis_operator', 'ml_team'] },
  MARKET: { name: 'Market', workflow: 'Market price intelligence', endpoint: 'POST /api/v1/agents/market/prices', roles: ['admin', 'gis_operator', 'ml_team'] },
  SCHEME: { name: 'Scheme', workflow: 'Government scheme screening', endpoint: 'POST /api/v1/agents/schemes/screen', roles: ['admin', 'gis_operator', 'ml_team'] },
  ESCALATION: { name: 'Escalation', workflow: 'Escalation screening', endpoint: 'POST /api/v1/agents/escalation/screen', roles: ['admin', 'gis_operator', 'ml_team'] },
  LEARNING: { name: 'Learning', workflow: 'Manual evidence review', endpoint: 'POST /api/v1/agents/learning/review', roles: ['admin', 'ml_team'] }
});

export function normalizeAgentIds(values) {
  if (!Array.isArray(values)) return [];
  return [...new Set(values.filter(value => typeof value === 'string' && IDENTIFIER.test(value)))];
}

export function normalizeAgentRecords(values, role) {
  if (!Array.isArray(values)) return [];
  const seen = new Set();
  return values.flatMap(value => {
    if (!value || typeof value !== 'object') return [];
    const definition = AGENT_DEFINITIONS[value.id];
    if (!definition || seen.has(value.id)) return [];
    if (typeof value.status !== 'string' || typeof value.execution_enabled !== 'boolean' || typeof value.learning_enabled !== 'boolean') return [];
    seen.add(value.id);
    return [{
      id: value.id, name: definition.name, status: value.status,
      executionEnabled: value.execution_enabled,
      learningEnabled: value.learning_enabled,
      genericExecutionAvailable: false,
      routeRegistered: true,
      runtimeReadiness: 'not_verified',
      workflow: definition.workflow, endpoint: definition.endpoint,
      roleAuthorized: definition.roles.includes(role)
    }];
  });
}

export function summarizeAgentRecords(agents) {
  return {
    total: agents.length,
    enabled: agents.filter(agent => agent.status.toLowerCase() === 'enabled').length,
    disabled: agents.filter(agent => agent.status.toLowerCase() === 'disabled').length,
    routes: agents.filter(agent => agent.routeRegistered).length
  };
}

import React, { useEffect, useMemo, useState } from 'react';
import { useAuth } from './AuthContext.jsx';
import { loadAgentMetadata } from './agentApi.js';
import { normalizeAgentRecords, summarizeAgentRecords } from './agentCatalog.js';
import AgentIntakeWorkspace from './AgentIntakeWorkspace.jsx';
import AgentWeatherWorkspace from './AgentWeatherWorkspace.jsx';
import AgentCropAdvisoryWorkspace from './AgentCropAdvisoryWorkspace.jsx';
import AgentMarketWorkspace from './AgentMarketWorkspace.jsx';
import AgentSchemeWorkspace from './AgentSchemeWorkspace.jsx';
import AgentEscalationWorkspace from './AgentEscalationWorkspace.jsx';
import AgentLearningWorkspace from './AgentLearningWorkspace.jsx';

const PRIVILEGED_ROLES = ['admin', 'gis_operator', 'ml_team'];

function Capability({ enabled, enabledText = 'Available', disabledText = 'Unavailable' }) {
  return <span className={enabled ? 'agent-capability is-available' : 'agent-capability is-unavailable'}>{enabled ? enabledText : disabledText}</span>;
}

export default function AgentGovernance() {
  const { session, request } = useAuth();
  const role = session?.principal.role;
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!session || !PRIVILEGED_ROLES.includes(role)) return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    setRecords([]);
    loadAgentMetadata(request, controller.signal)
      .then(data => { if (!controller.signal.aborted) setRecords(data); })
      .catch(reason => { if (reason?.name !== 'AbortError') setError(reason?.message || 'Agent metadata is unavailable.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [session, role, request]);

  const agents = useMemo(() => normalizeAgentRecords(records, role), [records, role]);
  const summary = useMemo(() => summarizeAgentRecords(agents), [agents]);

  if (!session) return <section className="agents-workspace"><div className="agents-panel"><h1>AI Agents</h1><p>Sign in with an authorized Admin, GIS Operator, or ML Team account.</p></div></section>;
  if (!PRIVILEGED_ROLES.includes(role)) return <section className="agents-workspace"><div className="agents-panel"><h1>AI Agents</h1><p className="gis-error" role="alert">Your account is not authorized to review agent governance.</p></div></section>;

  return (
    <section className="agents-workspace">
      <div className="agents-heading">
        <div>
          <span className="eyebrow">GOVERNED AI</span>
          <h1>Agent metadata</h1>
          <p>Authenticated registry configuration and separately governed dedicated workflows. Generic execution remains unavailable.</p>
        </div>
        <span className="agent-status">Automatic learning disabled</span>
      </div>

      {loading && <div className="agent-state" role="status">Loading agent metadata…</div>}
      {error && <div className="agent-state agent-state-error" role="alert">{error}</div>}
      {!loading && !error && agents.length === 0 && <div className="agent-state" role="status">No verified agent metadata is available.</div>}

      {agents.length > 0 && <div className="agent-summary" aria-label="Agent registry summary">
        <div><span>Total agents</span><strong>{summary.total}</strong></div>
        <div><span>Configured enabled</span><strong>{summary.enabled}</strong></div>
        <div><span>Configured disabled</span><strong>{summary.disabled}</strong></div>
        <div><span>Dedicated routes</span><strong>{summary.routes}</strong></div>
      </div>}

      {agents.length > 0 && <div className="agent-grid" aria-label="Registered agents">
        {agents.map(agent => <article className="agent-card" key={agent.id}>
          <div className="agent-card-head">
            <div><span className="agent-id">{agent.id}</span><h2>{agent.name}</h2></div>
            <span className={`agent-config-status status-${agent.status.toLowerCase()}`}>{agent.status}</span>
          </div>
          <dl className="agent-facts">
            <div><dt>Configured execution</dt><dd><Capability enabled={agent.executionEnabled} enabledText="Enabled" disabledText="Disabled" /></dd></div>
            <div><dt>Generic execution</dt><dd><Capability enabled={agent.genericExecutionAvailable} /></dd></div>
            <div><dt>Dedicated API route</dt><dd><Capability enabled={agent.routeRegistered} enabledText="Route registered" /></dd></div>
            <div><dt>Runtime readiness</dt><dd><span className="agent-capability is-neutral">Not verified</span></dd></div>
            <div><dt>Learning capability</dt><dd><Capability enabled={agent.learningEnabled} enabledText="Enabled" disabledText="Disabled" /></dd></div>
          </dl>
          <details className="agent-details">
            <summary>View verified details</summary>
            <dl>
              <div><dt>Agent ID</dt><dd>{agent.id}</dd></div>
              <div><dt>Registered workflow</dt><dd>{agent.workflow}</dd></div>
              <div><dt>Dedicated API route</dt><dd><code>{agent.endpoint}</code></dd></div>
              <div><dt>Current role access</dt><dd>{agent.roleAuthorized ? 'Authorized' : 'Not authorized'}</dd></div>
              <div><dt>Runtime readiness</dt><dd>Not verified by metadata API</dd></div>
            </dl>
            {!agent.roleAuthorized && <p className="agent-inline-note">This registered route is not authorized for your current role.</p>}
          </details>
        </article>)}
      </div>}

      <AgentIntakeWorkspace />
      <AgentWeatherWorkspace />
      <AgentCropAdvisoryWorkspace />
      <AgentMarketWorkspace />
      <AgentSchemeWorkspace />
      <AgentEscalationWorkspace />
      {role !== 'gis_operator' && <AgentLearningWorkspace />}
      <section className="agents-panel learning-panel" aria-labelledby="learning-title">
        <h2 id="learning-title">Governed learning</h2>
        <p><strong>Automatic learning and model training are disabled.</strong> The dedicated Learning workflow performs a manual evidence review only; it does not update or train a model.</p>
      </section>
    </section>
  );
}

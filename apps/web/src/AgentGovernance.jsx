import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  LayoutGrid,
  ClipboardList,
  CloudSun,
  Sprout,
  ChartNoAxesCombined,
  Landmark,
  MessagesSquare,
  BrainCircuit,
  ShieldCheck,
  Search,
  CheckCircle,
  CircleOff,
  Workflow
} from 'lucide-react';

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
  const [search, setSearch] = useState('');
  const [configFilter, setConfigFilter] = useState('all');

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

  const term = search.trim().toLowerCase();

  const filteredAgents = agents.filter(agent => {

    const matchesSearch = [
      agent.id,
      agent.name,
      agent.workflow,
      agent.status
    ].some(value =>
      String(value ?? '').toLowerCase().includes(term)
    );

    const matchesConfig =
      configFilter === 'all' ||
      (configFilter === 'enabled' && agent.executionEnabled) ||
      (configFilter === 'disabled' && !agent.executionEnabled);

    return matchesSearch && matchesConfig;
  });

  if (!session) return <section className="agents-workspace"><div className="agents-panel"><h1>AI Agents</h1><p>Sign in with an authorized Admin, GIS Operator, or ML Team account.</p></div></section>;
  if (!PRIVILEGED_ROLES.includes(role)) return <section className="agents-workspace"><div className="agents-panel"><h1>AI Agents</h1><p className="gis-error" role="alert">Your account is not authorized to review agent governance.</p></div></section>;

  return (
    <section className="agents-workspace agents-modern-workspace">
      <div className="agents-modern-heading">

  <div>
    <span className="agents-modern-label">
      <ShieldCheck size={18} aria-hidden="true" />
      Agricultural AI workspace
    </span>

    <h1>AI Agents</h1>

    <p>
      Explore registered agents and dedicated
      agricultural workflows.
    </p>

    <span className="agent-status">
      Automatic learning disabled
    </span>
  </div>

  <div className="agents-modern-art" aria-hidden="true">
    <Bot size={90} strokeWidth={1.3} />
  </div>

</div>
{loading && <div className="agent-state" role="status">Loading agent metadata…</div>}
      {error && <div className="agent-state agent-state-error" role="alert">{error}</div>}
      {!loading && !error && agents.length === 0 && <div className="agent-state" role="status">No verified agent metadata is available.</div>}

      {agents.length > 0 && <div className="agent-summary" aria-label="Agent registry summary">
        <div className="agent-summary-blue">
          <Bot size={25} aria-hidden="true" />
          <strong>{summary.total}</strong>
          <span>Total agents</span>
        </div>

        <div className="agent-summary-green">
          <CheckCircle size={25} aria-hidden="true" />
          <strong>{summary.enabled}</strong>
          <span>Configured enabled</span>
        </div>

        <div className="agent-summary-orange">
          <CircleOff size={25} aria-hidden="true" />
          <strong>{summary.disabled}</strong>
          <span>Configured disabled</span>
        </div>

        <div className="agent-summary-purple">
          <Workflow size={25} aria-hidden="true" />
          <strong>{summary.routes}</strong>
          <span>Dedicated routes</span>
        </div>
      </div>}

      {agents.length > 0 && (

  <div className="agent-registry-toolbar">

    <div>
      <h2>Registered agents</h2>
      <p>{filteredAgents.length} of {agents.length} agents</p>
    </div>

    <div className="agent-filter-row">

      <div className="agent-search">
        <Search size={19} aria-hidden="true" />

        <input
          type="search"
          aria-label="Search registered agents"
          placeholder="Search agents..."
          value={search}
          onChange={event => setSearch(event.target.value)}
        />
      </div>

      <select
        aria-label="Filter agent configuration"
        value={configFilter}
        onChange={event => setConfigFilter(event.target.value)}
      >
        <option value="all">All configurations</option>
        <option value="enabled">Configured enabled</option>
        <option value="disabled">Configured disabled</option>
      </select>

    </div>

  </div>
)}

{agents.length > 0 && filteredAgents.length === 0 && (
  <div className="agent-state" role="status">
    No agents match your search or filter.
  </div>
)}

{filteredAgents.length > 0 && <div className="agent-grid" aria-label="Registered agents">
        {filteredAgents.map(agent => <article className="agent-card" key={agent.id}>
          <div className="agent-card-head">
            <div className="agent-card-identity">

  <span className="agent-card-icon">
    <Bot size={25} aria-hidden="true" />
  </span>

  <div>
    <h2>{agent.name}</h2>
    <span className="agent-id">{agent.id}</span>
  </div>

</div>
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

      <div className="agent-workflow-heading">
        <h2>Dedicated agent workflows</h2>
        <p>Select a workflow to access its existing interface.</p>
      </div>

      <nav
        className="agent-workflow-navigation"
        aria-label="Dedicated agent workflows"
      >

        {[
          ['intake', 'Farmer Intake', ClipboardList],
          ['weather', 'Weather Intelligence', CloudSun],
          ['crop', 'Crop Advisory', Sprout],
          ['market', 'Market Intelligence', ChartNoAxesCombined],
          ['scheme', 'Government Schemes', Landmark],
          ['escalation', 'Escalation', MessagesSquare],
          ...(role !== 'gis_operator'
            ? [['learning', 'Governed Learning', BrainCircuit]]
            : [])
        ].map(([id, label, Icon]) => (

          <button
            type="button"
            key={id}
            onClick={() => document
              .getElementById(`agent-workflow-${id}`)
              ?.scrollIntoView({ block: 'start' })}
          >
            <Icon size={23} aria-hidden="true" />
            <span>{label}</span>
          </button>

        ))}

      </nav>

      <div className="agent-workflow-section" id="agent-workflow-intake">
        <AgentIntakeWorkspace />
      </div>

      <div className="agent-workflow-section" id="agent-workflow-weather">
        <AgentWeatherWorkspace />
      </div>

      <div className="agent-workflow-section" id="agent-workflow-crop">
        <AgentCropAdvisoryWorkspace />
      </div>

      <div className="agent-workflow-section" id="agent-workflow-market">
        <AgentMarketWorkspace />
      </div>

      <div className="agent-workflow-section" id="agent-workflow-scheme">
        <AgentSchemeWorkspace />
      </div>

      <div className="agent-workflow-section" id="agent-workflow-escalation">
        <AgentEscalationWorkspace />
      </div>

      <div className="agent-workflow-section" id="agent-workflow-learning" hidden={role === 'gis_operator'}>
        {role !== 'gis_operator' && <AgentLearningWorkspace />}
      </div>
      <section className="agents-panel learning-panel" aria-labelledby="learning-title">
        <h2 id="learning-title">Governed learning</h2>
        <p><strong>Automatic learning and model training are disabled.</strong> The dedicated Learning workflow performs a manual evidence review only; it does not update or train a model.</p>
      </section>
    </section>
  );
}

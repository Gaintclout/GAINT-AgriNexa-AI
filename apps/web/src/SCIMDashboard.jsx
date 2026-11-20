import React, { useCallback, useEffect, useState } from 'react';
import SpectralIndices from './SpectralIndices.jsx';
import SCIMJobPlanning from './SCIMJobPlanning.jsx';
import SCIMParcelIntelligence from './SCIMParcelIntelligence.jsx';
import { useAuth } from './AuthContext.jsx';
import { API } from './gisApi.js';

const STATUSES = ['', 'planned', 'queued', 'running', 'succeeded', 'failed', 'cancelled'];
const initialSearch = { provider: '', west: '', south: '', east: '', north: '', start: '', end: '', max_cloud_percent: '30', limit: '20' };

async function parseApi(response) {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail) ? detail.map(item => `${(item.loc || []).join('.')}: ${item.msg}`).join('; ') : typeof detail === 'string' ? detail : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

function JsonDetails({ value }) {
  return <pre className="scim-json">{JSON.stringify(value, null, 2) ?? 'No data returned'}</pre>;
}

export default function SCIMDashboard() {
  const { session, request } = useAuth();
  const api = useCallback((path, options = {}) => request(path, options).then(parseApi), [request]);
  const [tab, setTab] = useState('catalog');
  const [providers, setProviders] = useState([]);
  const [providerError, setProviderError] = useState('');
  const [assessmentForm, setAssessmentForm] = useState({ provider: '', scene_id: '', captured_at: '', cloud_cover_percent: '10', west: '', south: '', east: '', north: '', max_cloud_percent: '30' });
  const [assessmentResult, setAssessmentResult] = useState(null);
  const [assessmentError, setAssessmentError] = useState('');
  const [assessmentBusy, setAssessmentBusy] = useState(false);
  const [form, setForm] = useState(initialSearch);
  const [discoveryMode, setDiscoveryMode] = useState('discover');
  const [scenes, setScenes] = useState(null);
  const [catalogError, setCatalogError] = useState('');
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [stages, setStages] = useState(null);
  const [stagesError, setStagesError] = useState('');
  const [stagesBusy, setStagesBusy] = useState(false);
  const [jobs, setJobs] = useState(null);
  const [jobsError, setJobsError] = useState('');
  const [jobsBusy, setJobsBusy] = useState(false);
  const [filters, setFilters] = useState({ parcel_id: '', status: '', limit: '20', offset: '0' });
  const [selectedJob, setSelectedJob] = useState(null);
  const [jobId, setJobId] = useState('');
  const [jobError, setJobError] = useState('');
  const [jobBusy, setJobBusy] = useState(false);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [cancelMessage, setCancelMessage] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/openapi.json`, { signal: controller.signal }).then(parseApi).then(spec => {
      const provider = spec?.components?.schemas?.SatelliteProvider;
      const values = provider?.enum || [];
      if (!controller.signal.aborted) setProviders(Array.isArray(values) ? values : []);
    }).catch(error => {
      if (!controller.signal.aborted && error.name !== 'AbortError') setProviderError('Provider options unavailable. Enter a backend-supported provider value.');
    });
    return () => controller.abort();
  }, []);

  async function assessScene(event) {
    event.preventDefault();
    setAssessmentError('');
    setAssessmentResult(null);
    const f = assessmentForm;
    const bounds = ['west', 'south', 'east', 'north'].map(key => Number(f[key]));
    const cloud = Number(f.cloud_cover_percent);
    const maxCloud = Number(f.max_cloud_percent);
    if (!f.provider.trim() || !f.scene_id.trim() || !f.captured_at || ['west','south','east','north'].some(key => f[key] === '')) {
      setAssessmentError('Provider, scene ID, capture time and all bounds are required.'); return;
    }
    if (!/^[A-Za-z0-9_.:-]{1,200}$/.test(f.scene_id.trim())) {
      setAssessmentError('Scene ID may contain letters, numbers, underscore, dot, colon and hyphen only.'); return;
    }
    const [west,south,east,north] = bounds;
    if (!bounds.every(Number.isFinite) || west < -180 || west > 180 || east < -180 || east > 180 || south < -90 || south > 90 || north < -90 || north > 90 || west >= east || south >= north || !Number.isFinite(cloud) || cloud < 0 || cloud > 100 || !Number.isFinite(maxCloud) || maxCloud < 0 || maxCloud > 100) {
      setAssessmentError('Check bounds and cloud percentages (0–100).'); return;
    }
    const captured = new Date(f.captured_at);
    if (Number.isNaN(captured.getTime())) { setAssessmentError('Invalid capture date.'); return; }
    setAssessmentBusy(true);
    try {
      const result = await api(`/api/v1/scim/scenes/assess?max_cloud_percent=${encodeURIComponent(maxCloud)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: f.provider.trim(), scene_id: f.scene_id.trim(), captured_at: captured.toISOString(), cloud_cover_percent: cloud, west, south, east, north })
      });
      setAssessmentResult(result);
    } catch (error) { setAssessmentError(error.message); }
    finally { setAssessmentBusy(false); }
  }

  const loadStages = useCallback(async signal => {
    setStagesBusy(true);
    setStagesError('');
    try {
      const result = await api('/api/v1/scim/processing/stages', { signal });
      if (!signal?.aborted) setStages(result);
    } catch (error) {
      if (error.name !== 'AbortError' && !signal?.aborted) setStagesError(error.message);
    } finally {
      if (!signal?.aborted) setStagesBusy(false);
    }
  }, [api]);

  useEffect(() => {
    const controller = new AbortController();
    loadStages(controller.signal);
    return () => controller.abort();
  }, [loadStages]);

  async function discover(event) {
    event.preventDefault();
    setCatalogError('');
    const west = Number(form.west), east = Number(form.east);
    const south = Number(form.south), north = Number(form.north);
    const cloud = Number(form.max_cloud_percent), limit = Number(form.limit);
    if (!form.provider.trim() || [form.west, form.south, form.east, form.north, form.start, form.end].some(value => !value.trim())) {
      setCatalogError('Enter a provider, all four geographic bounds and both dates.'); return;
    }
    if (![west, south, east, north, cloud, limit].every(Number.isFinite) || west < -180 || west > 180 || east < -180 || east > 180 || south < -90 || south > 90 || north < -90 || north > 90 || west >= east || south >= north || cloud < 0 || cloud > 100 || !Number.isInteger(limit) || limit < 1 || limit > 100) {
      setCatalogError('Check bounding coordinates, cloud cover (0–100) and limit (1–100).'); return;
    }
    if (!Number.isFinite(Date.parse(form.start)) || !Number.isFinite(Date.parse(form.end)) || Date.parse(form.start) >= Date.parse(form.end)) { setCatalogError('Enter valid dates; start must be earlier than end.'); return; }
    const body = { provider: form.provider.trim(), west, south, east, north, start: new Date(form.start).toISOString(), end: new Date(form.end).toISOString(), max_cloud_percent: cloud, limit };
    setCatalogBusy(true);
    setScenes(null);
    try {
      const data = await api(`/api/v1/scim/catalog/${discoveryMode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      setScenes(data);
    } catch (error) { setCatalogError(error.message); }
    finally { setCatalogBusy(false); }
  }

  async function loadJobs(event) {
    event?.preventDefault();
    setJobsError('');
    const limit = Number(filters.limit), offset = Number(filters.offset);
    if (!Number.isInteger(limit) || limit < 1 || limit > 100 || !Number.isInteger(offset) || offset < 0 || (filters.parcel_id && filters.parcel_id.length > 36)) {
      setJobsError('Use limit 1–100, offset 0 or greater, and parcel ID up to 36 characters.'); return;
    }
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filters.status) query.set('status', filters.status);
    if (filters.parcel_id.trim()) query.set('parcel_id', filters.parcel_id.trim());
    setJobsBusy(true);
    try { setJobs(await api(`/api/v1/scim/jobs?${query}`)); }
    catch (error) { setJobsError(error.message); }
    finally { setJobsBusy(false); }
  }

  async function loadJob(event) {
    event.preventDefault();
    setJobError('');
    if (!jobId.trim()) { setJobError('Enter a job ID.'); return; }
    setJobBusy(true);
    try { setSelectedJob(await api(`/api/v1/scim/jobs/${encodeURIComponent(jobId.trim())}`)); }
    catch (error) { setJobError(error.message); }
    finally { setJobBusy(false); }
  }

  async function cancelJob() {
    const id = jobId.trim();
    setJobError(''); setCancelMessage('');
    if (!id) { setJobError('Enter a job ID to cancel.'); return; }
    if (!window.confirm(`Request cancellation of SCIM job ${id}?`)) return;
    setCancelBusy(true);
    try {
      const response = await api(`/api/v1/scim/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
      setCancelMessage('Cancellation request accepted by backend.');
      setSelectedJob(response);
      try { const query = new URLSearchParams({ limit: String(filters.limit), offset: String(filters.offset) }); if (filters.status) query.set('status', filters.status); if (filters.parcel_id.trim()) query.set('parcel_id', filters.parcel_id.trim()); setJobs(await api(`/api/v1/scim/jobs?${query}`)); }
      catch (refreshError) { setJobsError(`Cancellation succeeded, but job list refresh failed: ${refreshError.message}`); }
    } catch (error) { setJobError(error.message); }
    finally { setCancelBusy(false); }
  }

  const sceneRows = Array.isArray(scenes?.scenes) ? scenes.scenes : [];
  if (!session) return <section className="scim-workspace"><div className="scim-panel"><h2>SCIM Intelligence</h2><p>Sign in above with an authorized SCIM account.</p></div></section>;
  if (!['admin','gis_operator','ml_team'].includes(session.principal.role)) return <section className="scim-workspace"><div className="scim-panel"><h2>SCIM Intelligence</h2><p className="scim-error">Your account is not authorized for SCIM.</p></div></section>;
  return <section className="scim-workspace">
    <div className="scim-heading"><div><h2>SCIM Intelligence</h2><p>Satellite catalogue discovery, processing stages and job monitoring</p></div><span className="scim-kicker">Live backend integration</span></div>
    <div className="scim-tabs" role="tablist" aria-label="SCIM sections">
      {[['catalog', 'Satellite Catalogue'], ['assessment', 'Scene Assessment'], ['indices', 'Spectral Indices'], ['planning', 'Job Planning'], ['summary', 'Parcel Summary'], ['assets', 'Asset Review'], ['stages', 'Processing Stages'], ['jobs', 'SCIM Jobs']].map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>)}
    </div>
    {tab === 'catalog' && <div className="scim-panel">
      <h3>Discover satellite scenes</h3>
      <p className="scim-muted">Provider must match the SatelliteProvider enum in your backend. The uploaded schema did not include its allowed values.</p>
      {providerError && <p className="scim-muted">{providerError}</p>}
      <form className="scim-form" onSubmit={discover}>
        <label>Satellite provider{providers.length ? <select required value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })}><option value="">Select provider</option>{providers.map(value => <option key={value} value={value}>{value}</option>)}</select> : <input required value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} placeholder="Backend provider value" />}</label>
        <label>Discovery mode<select value={discoveryMode} onChange={e => setDiscoveryMode(e.target.value)}><option value="discover">Discover</option><option value="discover-ranked">Ranked discovery</option></select></label>
        {['west', 'south', 'east', 'north'].map(field => <label key={field}>{field.charAt(0).toUpperCase() + field.slice(1)}<input type="number" step="any" required value={form[field]} onChange={e => setForm({ ...form, [field]: e.target.value })} /></label>)}
        <label>Start (local time)<input type="datetime-local" required value={form.start} onChange={e => setForm({ ...form, start: e.target.value })} /></label>
        <label>End (local time)<input type="datetime-local" required value={form.end} onChange={e => setForm({ ...form, end: e.target.value })} /></label>
        <label>Max cloud (%)<input type="number" min="0" max="100" step="any" required value={form.max_cloud_percent} onChange={e => setForm({ ...form, max_cloud_percent: e.target.value })} /></label>
        <label>Scene limit<input type="number" min="1" max="100" step="1" required value={form.limit} onChange={e => setForm({ ...form, limit: e.target.value })} /></label>
        <div className="scim-form-actions"><button disabled={catalogBusy} type="submit">{catalogBusy ? 'Searching...' : 'Discover Scenes'}</button></div>
      </form>
      {catalogError && <p className="scim-error" role="alert">{catalogError}</p>}
      {scenes && <div className="scim-results"><h3>Discovery Results</h3><p className="scim-muted">Returned: {scenes.returned ?? sceneRows.length} · Truncated: {scenes.truncated ? 'Yes' : 'No'}</p><div className="scim-table-wrap"><table><thead><tr><th>Scene ID</th><th>Collection</th><th>Captured</th><th>Cloud %</th><th>Bands</th><th>Assets</th></tr></thead><tbody>{sceneRows.map((scene, index) => <tr key={`${scene.scene_id}-${index}`}><td>{scene.scene_id}</td><td>{scene.collection}</td><td>{scene.captured_at ? new Date(scene.captured_at).toLocaleString() : '—'}</td><td>{scene.cloud_cover_percent ?? '—'}</td><td>{(scene.available_bands || []).join(', ') || '—'}</td><td>{scene.assets_complete ? 'Complete' : 'Incomplete'}</td></tr>)}{!sceneRows.length && <tr><td colSpan="6">No scenes returned.</td></tr>}</tbody></table></div></div>}
    </div>}
    {tab === 'assessment' && <div className="scim-panel">
      <h3>Scene Quality Assessment</h3>
      <p className="scim-muted">Assess one candidate satellite scene against the backend's cloud-cover and geographic checks.</p>
      <form className="scim-form" onSubmit={assessScene}>
        <label>Provider{providers.length ? <select required value={assessmentForm.provider} onChange={e => setAssessmentForm({ ...assessmentForm, provider: e.target.value })}><option value="">Select provider</option>{providers.map(value => <option key={value} value={value}>{value}</option>)}</select> : <input required value={assessmentForm.provider} onChange={e => setAssessmentForm({ ...assessmentForm, provider: e.target.value })} placeholder="Backend provider value" />}</label>
        <label>Scene ID<input required maxLength={200} value={assessmentForm.scene_id} onChange={e => setAssessmentForm({ ...assessmentForm, scene_id: e.target.value })} placeholder="Scene identifier" /></label>
        <label>Captured at (local time)<input type="datetime-local" required value={assessmentForm.captured_at} onChange={e => setAssessmentForm({ ...assessmentForm, captured_at: e.target.value })} /></label>
        <label>Scene cloud cover (%)<input type="number" min="0" max="100" step="any" required value={assessmentForm.cloud_cover_percent} onChange={e => setAssessmentForm({ ...assessmentForm, cloud_cover_percent: e.target.value })} /></label>
        {['west', 'south', 'east', 'north'].map(key => <label key={key}>{key.charAt(0).toUpperCase() + key.slice(1)}<input type="number" step="any" required value={assessmentForm[key]} onChange={e => setAssessmentForm({ ...assessmentForm, [key]: e.target.value })} /></label>)}
        <label>Maximum allowed cloud (%)<input type="number" min="0" max="100" step="any" required value={assessmentForm.max_cloud_percent} onChange={e => setAssessmentForm({ ...assessmentForm, max_cloud_percent: e.target.value })} /></label>
        <div className="scim-form-actions"><button type="submit" disabled={assessmentBusy}>{assessmentBusy ? 'Assessing...' : 'Assess Scene'}</button></div>
      </form>
      {assessmentError && <p className="scim-error" role="alert">{assessmentError}</p>}
      {assessmentResult && <div className="scim-results" role="status"><h3>{assessmentResult.usable ? 'Usable scene' : 'Scene not usable'}</h3><p>Scene: {assessmentResult.scene_id}</p><p>Cloud cover: {assessmentResult.cloud_cover_percent}%</p><p>Reasons: {Array.isArray(assessmentResult.reasons) && assessmentResult.reasons.length ? assessmentResult.reasons.join('; ') : 'No reasons reported'}</p></div>}
    </div>}
    {tab === 'indices' && <SpectralIndices request={request} />}
    {tab === 'planning' && <SCIMJobPlanning request={request} />}
    {tab === 'summary' && <SCIMParcelIntelligence mode="summary" request={request} />}
    {tab === 'assets' && <SCIMParcelIntelligence mode="assets" request={request} />}
    {tab === 'stages' && <div className="scim-panel"><div className="scim-panel-head"><h3>Processing Stages</h3><button type="button" disabled={stagesBusy} onClick={() => loadStages()}>{stagesBusy ? 'Loading...' : 'Refresh'}</button></div>{stagesError && <p className="scim-error" role="alert">{stagesError}</p>}{stages !== null && <JsonDetails value={stages} />}{!stagesBusy && stages === null && !stagesError && <p className="scim-muted">No stage data available.</p>}</div>}
    {tab === 'jobs' && <div className="scim-panel"><h3>Job Monitoring</h3><form className="scim-form" onSubmit={loadJobs}><label>Parcel ID (optional)<input value={filters.parcel_id} onChange={e => setFilters({ ...filters, parcel_id: e.target.value })} /></label><label>Status<select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}>{STATUSES.map(status => <option key={status} value={status}>{status || 'All statuses'}</option>)}</select></label><label>Limit<input type="number" min="1" max="100" value={filters.limit} onChange={e => setFilters({ ...filters, limit: e.target.value })} /></label><label>Offset<input type="number" min="0" value={filters.offset} onChange={e => setFilters({ ...filters, offset: e.target.value })} /></label><div className="scim-form-actions"><button disabled={jobsBusy} type="submit">{jobsBusy ? 'Loading...' : 'Load Jobs'}</button></div></form>{jobsError && <p className="scim-error" role="alert">{jobsError}</p>}{jobs !== null && <div className="scim-results"><h3>Backend Job Response</h3><JsonDetails value={jobs} /></div>}<div className="scim-job-detail"><h3>Inspect Job by ID</h3><form className="scim-inline-form" onSubmit={loadJob}><input aria-label="Job ID" placeholder="Enter job ID" value={jobId} onChange={e => setJobId(e.target.value)} /><button disabled={jobBusy} type="submit">{jobBusy ? 'Loading...' : 'Inspect Job'}</button></form><div className="scim-plan-actions"><button type="button" disabled={cancelBusy || jobBusy || !jobId.trim()} onClick={cancelJob}>{cancelBusy ? 'Cancelling...' : 'Cancel Job'}</button></div>{cancelMessage && <p className="registry-success" role="status">{cancelMessage}</p>}{jobError && <p className="scim-error" role="alert">{jobError}</p>}{selectedJob !== null && <JsonDetails value={selectedJob} />}</div></div>}
  </section>;
}

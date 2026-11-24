import React, { useEffect, useState } from 'react';
import { API } from './gisApi.js';

const ENDPOINTS = {
  summary: { title: 'Parcel spectral summary', path: '/api/v1/scim/parcels/summarize-samples', schema: 'ParcelSummaryRequest' },
  assets: { title: 'Satellite asset review', path: '/api/v1/scim/assets/review', schema: 'AssetReviewRequest' }
};

function describeError(payload, status) {
  const detail = payload?.detail;
  if (Array.isArray(detail)) return detail.map(item => `${(item.loc || []).join('.')}: ${item.msg}`).join('; ');
  if (typeof detail === 'string') return detail;
  return `Request failed (HTTP ${status})`;
}

function schemaDescription(spec, name) {
  const schemas = spec?.components?.schemas || {};
  const schema = schemas[name];
  if (!schema) return null;
  const required = new Set(schema.required || []);
  return Object.entries(schema.properties || {}).map(([key, value]) => {
    const referenced = value.$ref?.split('/').pop();
    const definition = referenced ? schemas[referenced] : value;
    const type = definition?.enum ? `enum: ${definition.enum.join(', ')}` : definition?.type || (value.anyOf ? 'multiple types' : 'object');
    return { key, required: required.has(key), type };
  });
}

export default function SCIMParcelIntelligence({ mode = 'summary', request }) {
  const config = ENDPOINTS[mode] || ENDPOINTS.summary;
  const [schema, setSchema] = useState(null);
  const [schemaError, setSchemaError] = useState('');
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setSchema(null);
    setSchemaError('');
    setResult(null);
    setError('');
    setInput('');
    fetch(`${API}/openapi.json`, { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`OpenAPI unavailable (HTTP ${response.status})`);
        return response.json();
      })
      .then(spec => {
        if (controller.signal.aborted) return;
        const details = schemaDescription(spec, config.schema);
        if (!details) throw new Error(`${config.schema} is not available in the backend OpenAPI schema.`);
        setSchema(details);
        if (mode === 'assets') setInput(JSON.stringify({ provider: '', assets: {} }, null, 2));
        else {
          const required = spec.components.schemas[config.schema].required || [];
          setInput(JSON.stringify(Object.fromEntries(required.map(key => [key, key === 'samples' ? [] : ''])), null, 2));
        }
      })
      .catch(e => { if (!controller.signal.aborted) setSchemaError(e.message); });
    return () => controller.abort();
  }, [mode, config.schema]);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    if (!schema) { setError('Backend schema is unavailable. Cannot submit an unverified request.'); return; }
    let payload;
    try { payload = JSON.parse(input); }
    catch { setError('Enter valid JSON.'); return; }
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
      setError('Request must be a JSON object.'); return;
    }
    const missing = schema.filter(field => field.required && (payload[field.key] === undefined || payload[field.key] === null || payload[field.key] === ''));
    if (missing.length) { setError(`Required fields missing: ${missing.map(field => field.key).join(', ')}`); return; }
    setBusy(true);
    try {
      const response = await request(config.path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(describeError(data, response.status));
      setResult(data ?? { message: 'Request completed; backend returned no JSON body.' });
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <section className="scim-panel scim-modern-parcel">
    <h3>{config.title}</h3>
    <p className="scim-muted">Review the required input fields and submit actual measurements or satellite asset information.</p>
    {schemaError && <p className="scim-error" role="alert">{schemaError}</p>}
    {!schema && !schemaError && (
  <p className="scim-muted" role="status">
    Loading request fields...
  </p>
)}

{schema && <div className="scim-schema-fields">
      <h4>Request fields ({config.schema})</h4>
      <div className="scim-table-wrap"><table><thead><tr><th>Field</th><th>Type</th><th>Required</th></tr></thead>
        <tbody>{schema.map(field => <tr key={field.key}><td>{field.key}</td><td>{field.type}</td><td>{field.required ? 'Yes' : 'No'}</td></tr>)}</tbody>
      </table></div>
    </div>}
    <form onSubmit={submit} className="scim-json-form">
      <label htmlFor={`scim-payload-${mode}`}>Request editor (JSON)</label>
      <textarea id={`scim-payload-${mode}`} spellCheck="false" rows="12" value={input} onChange={e => setInput(e.target.value)} placeholder="Load backend schema to prepare request" disabled={!schema || busy} />
      <div className="scim-form-actions"><button type="submit" disabled={!schema || busy}>{busy ? 'Processing...' : mode === 'assets' ? 'Review assets' : 'Calculate parcel summary'}</button></div>
    </form>
    {error && <p className="scim-error" role="alert">{error}</p>}
    {result !== null && <div className="scim-results" role="status"><h3>Request result</h3>
      {mode === 'summary' && result && typeof result === 'object' && <div className="scim-summary-metrics">
        {['parcel_id','total_samples','clear_samples','valid_samples','ndvi_median','ndwi_median','ndmi_median'].map(key => <div key={key}><span>{({parcel_id:'Parcel ID',total_samples:'Total samples',clear_samples:'Clear samples',valid_samples:'Valid samples',ndvi_median:'Median NDVI',ndwi_median:'Median NDWI',ndmi_median:'Median NDMI'})[key] || key}</span><strong>{result[key] == null ? '—' : String(result[key])}</strong></div>)}
      </div>}
      <details
  className="scim-technical-details"
  open={mode === 'assets'}
>
  <summary>View complete response</summary>

  <pre className="scim-json">
    {JSON.stringify(result, null, 2)}
  </pre>
</details>
    </div>}
  </section>;
}

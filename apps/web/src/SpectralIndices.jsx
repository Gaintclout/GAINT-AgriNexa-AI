import React, { useEffect, useMemo, useState } from 'react';
import { API } from './gisApi.js';

const MODES = [
  { id: 'calculate', label: 'Reflectance sample', path: '/api/v1/scim/indices/calculate' },
  { id: 'from-bands', label: 'Sensor bands', path: '/api/v1/scim/indices/from-bands' }
];

function resolveSchema(schema, definitions, depth = 0) {
  if (!schema || depth > 8) return schema || {};
  if (schema.$ref) {
    const name = schema.$ref.split('/').pop();
    return resolveSchema(definitions[name], definitions, depth + 1);
  }
  if (schema.anyOf) {
    const nonNull = schema.anyOf.find(item => item.type !== 'null');
    return resolveSchema(nonNull || {}, definitions, depth + 1);
  }
  if (schema.allOf?.length === 1) return resolveSchema(schema.allOf[0], definitions, depth + 1);
  return schema;
}

function readable(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, character => character.toUpperCase());
}

function getFields(schema, definitions) {
  const resolved = resolveSchema(schema, definitions);
  return Object.entries(resolved.properties || {}).map(([name, raw]) => {
    const item = resolveSchema(raw, definitions);
    return { name, item, required: (resolved.required || []).includes(name) };
  });
}

function parseValue(value, schema, name, required) {
  if (value.trim() === '') {
    if (required) throw new Error(`${readable(name)} is required.`);
    return undefined;
  }
  if (schema.type === 'number' || schema.type === 'integer') {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || (schema.type === 'integer' && !Number.isInteger(parsed))) throw new Error(`${readable(name)} must be a valid ${schema.type}.`);
    if (schema.minimum !== undefined && parsed < schema.minimum) throw new Error(`${readable(name)} must be at least ${schema.minimum}.`);
    if (schema.maximum !== undefined && parsed > schema.maximum) throw new Error(`${readable(name)} must be at most ${schema.maximum}.`);
    return parsed;
  }
  if (schema.type === 'boolean') return value === 'true';
  if (schema.type === 'array' || schema.type === 'object' || (!schema.type && !schema.enum)) {
    try {
      const parsed = JSON.parse(value);
      if (schema.type === 'array' && !Array.isArray(parsed)) throw new Error('Expected an array');
      if (schema.type === 'object' && (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object')) throw new Error('Expected an object');
      return parsed;
    } catch (error) { throw new Error(`${readable(name)} must contain valid JSON: ${error.message}`); }
  }
  if (schema.enum && !schema.enum.includes(value)) throw new Error(`Select a valid ${readable(name)}.`);
  if (schema.minLength && value.length < schema.minLength) throw new Error(`${readable(name)} is too short.`);
  if (schema.maxLength && value.length > schema.maxLength) throw new Error(`${readable(name)} is too long.`);
  if (schema.format === 'date-time' && Number.isNaN(Date.parse(value))) throw new Error(`${readable(name)} must be a valid date-time.`);
  return value;
}

export default function SpectralIndices({ request }) {
  const [mode, setMode] = useState('calculate');
  const [spec, setSpec] = useState(null);
  const [schemaError, setSchemaError] = useState('');
  const [values, setValues] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/openapi.json`, { signal: controller.signal })
      .then(async response => { if (!response.ok) throw new Error(`OpenAPI unavailable (${response.status})`); return response.json(); })
      .then(data => { if (!controller.signal.aborted) setSpec(data); })
      .catch(err => { if (err.name !== 'AbortError' && !controller.signal.aborted) setSchemaError(err.message); });
    return () => controller.abort();
  }, []);

  const selected = MODES.find(item => item.id === mode);
  const definitions = spec?.components?.schemas || {};
  const schema = spec?.paths?.[selected.path]?.post?.requestBody?.content?.['application/json']?.schema;
  const fields = useMemo(() => getFields(schema, definitions), [schema, spec]);

  function switchMode(next) {
    setMode(next);
    setValues({});
    setError('');
    setResult(null);
  }

  async function calculate(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    if (!schema || !fields.length) { setError('Request schema is unavailable. No request was submitted.'); return; }
    let payload;
    try {
      payload = {};
      for (const field of fields) {
        const parsed = parseValue(String(values[field.name] ?? ''), field.item, field.name, field.required);
        if (parsed !== undefined) payload[field.name] = parsed;
      }
    } catch (err) { setError(err.message); return; }
    setBusy(true);
    try {
      const response = await request(selected.path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = data?.detail;
        throw new Error(Array.isArray(detail) ? detail.map(item => `${(item.loc || []).join('.')}: ${item.msg}`).join('; ') : typeof detail === 'string' ? detail : `Request failed (${response.status})`);
      }
      setResult(data);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <div className="scim-panel">
    <h3>Spectral Index Calculation</h3>
    <p className="scim-muted">Calculate NDVI, NDWI and NDMI from backend-validated reflectance or sensor-band inputs. Field definitions load from the live FastAPI OpenAPI specification.</p>
    <div className="scim-tabs" role="group" aria-label="Index calculation method">
      {MODES.map(item => <button key={item.id} type="button" className={mode === item.id ? 'active' : ''} aria-pressed={mode === item.id} onClick={() => switchMode(item.id)}>{item.label}</button>)}
    </div>
    {schemaError && <p className="scim-error" role="alert">Unable to load input schema: {schemaError}. Check that the API is running and allows browser requests to /openapi.json.</p>}
    {!spec && !schemaError && <p className="scim-muted">Loading API field definitions...</p>}
    {spec && !fields.length && <p className="scim-error" role="alert">No supported fields found for this endpoint. Calculation disabled.</p>}
    {fields.length > 0 && <form className="scim-form" onSubmit={calculate}>
      {fields.map(({ name, item, required }) => <label key={name}>
        {readable(name)}{required ? ' *' : ''}
        {item.enum ? <select required={required} value={values[name] ?? ''} onChange={event => setValues(previous => ({ ...previous, [name]: event.target.value }))}>
          <option value="">Select {readable(name)}</option>
          {item.enum.map(option => <option key={String(option)} value={String(option)}>{String(option)}</option>)}
        </select> : item.type === 'boolean' ? <select required={required} value={values[name] ?? ''} onChange={event => setValues(previous => ({ ...previous, [name]: event.target.value }))}>
          <option value="">Select value</option><option value="true">True</option><option value="false">False</option>
        </select> : item.type === 'array' || item.type === 'object' || !item.type ? <textarea className="scim-textarea" required={required} value={values[name] ?? ''} placeholder={item.type === 'array' ? '[...]' : '{...}'} onChange={event => setValues(previous => ({ ...previous, [name]: event.target.value }))} /> : <input
          type={item.type === 'number' || item.type === 'integer' ? 'number' : 'text'}
          step={item.type === 'integer' ? '1' : item.type === 'number' ? 'any' : undefined}
          min={item.minimum} max={item.maximum} required={required}
          value={values[name] ?? ''}
          placeholder={item.description || readable(name)}
          onChange={event => setValues(previous => ({ ...previous, [name]: event.target.value }))}
        />}
        {item.description && <small className="scim-muted">{item.description}</small>}
      </label>)}
      <div className="scim-form-actions"><button type="submit" disabled={busy}>{busy ? 'Calculating...' : 'Calculate Indices'}</button></div>
    </form>}
    {error && <p className="scim-error" role="alert">{error}</p>}
    {result && <div className="scim-results" role="status">
      <h3>Calculated Indices</h3>
      <div className="scim-index-results">{['ndvi', 'ndwi', 'ndmi'].map(name => <div className="scim-index-card" key={name}><strong>{name.toUpperCase()}</strong><span>{typeof result[name] === 'number' ? result[name].toFixed(4) : 'Not available'}</span></div>)}</div>
      <p className="scim-muted">Values are returned by the backend; no client-side index estimates are substituted.</p>
      <pre className="scim-json">{JSON.stringify(result, null, 2)}</pre>
    </div>}
  </div>;
}

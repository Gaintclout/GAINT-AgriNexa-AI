import React, { useEffect, useState } from 'react';

import { enqueueEvidence, offlineDatabaseName, removeQueuedEvidence } from './fieldVerificationSync';

import FieldVerificationQueueSafe from './FieldVerificationQueueSafe';
import FieldVerifierSession from './FieldVerifierSession.jsx';
import { submitCompleteEvidence } from './fieldEvidenceSubmission.js';
import { useAuth } from './AuthContext.jsx';
import { API } from './gisApi.js';

const STORE = 'drafts';

const READY = 'ready_for_sync';

const DRAFT = 'local_draft';

const EMPTY = { parcel_id: '', observation: '', latitude: '', longitude: '', accuracy_m: '', captured_at: '', photo: null };

const queueId = id => id.replace(/-/g, '_');



function openDb(userId) {

  return new Promise((resolve, reject) => {

    if (!('indexedDB' in window)) return reject(new Error('IndexedDB is unavailable.'));

    const request = indexedDB.open(offlineDatabaseName('agrinexa-field-drafts-v2', userId), 1);

    request.onupgradeneeded = () => {

      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE, { keyPath: 'id' });

    };

    request.onsuccess = () => resolve(request.result);

    request.onerror = () => reject(request.error);

  });

}

async function dbOperation(userId, mode, action) {

  const db = await openDb(userId);

  try {

    return await new Promise((resolve, reject) => {

      const tx = db.transaction(STORE, mode);

      const request = action(tx.objectStore(STORE));

      tx.oncomplete = () => resolve(request?.result);

      tx.onerror = () => reject(tx.error || new Error('IndexedDB operation failed'));

      tx.onabort = () => reject(tx.error || new Error('IndexedDB transaction aborted'));

    });

  } finally { db.close(); }

}

const listDrafts = userId => dbOperation(userId, 'readonly', store => store.getAll());

const saveDraft = (item, userId) => dbOperation(userId, 'readwrite', store => store.put(item));

const deleteDraft = (id, userId) => dbOperation(userId, 'readwrite', store => store.delete(id));

const sorted = items => [...items].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''));



function readinessIssues(record) {

  const issues = [];

  if (!/^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$/.test(record.parcel_id || '')) issues.push('A valid parcel UUID is required.');

  if (!record.observation?.trim() || record.observation.length > 3000) issues.push('Observation must contain 1–3000 characters.');

  const lat = Number(record.latitude), lon = Number(record.longitude);

  if (record.latitude === '' || record.longitude === '' || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) issues.push('Valid GPS coordinates are required.');

  if (!record.captured_at || Number.isNaN(Date.parse(record.captured_at)) || Date.parse(record.captured_at) > Date.now()) issues.push('A valid GPS capture time is required.');

  if (!(record.photo instanceof Blob) || !record.photo.type.startsWith('image/') || record.photo.size > 8 * 1024 * 1024) issues.push('An evidence photo of at most 8 MB is required.');

  return issues;

}



export default function FieldVerification() {
  const { session: sharedSession, logout, request } = useAuth();
  const session = sharedSession?.principal.role === 'field_verifier' ? sharedSession : null;

  const [parcels, setParcels] = useState([]);
  const [syncBusy, setSyncBusy] = useState(false);

  const [form, setForm] = useState(EMPTY);

  const [drafts, setDrafts] = useState([]);

  const [error, setError] = useState('');

  const [notice, setNotice] = useState('');

  const [gpsBusy, setGpsBusy] = useState(false);

  const [saving, setSaving] = useState(false);

  const [busyId, setBusyId] = useState(null);

  const [loading, setLoading] = useState(true);

  const [editingId, setEditingId] = useState(null);

  const [photoUrl, setPhotoUrl] = useState('');
  const [queueRefreshKey, setQueueRefreshKey] = useState(0);
  const refreshQueue = () => setQueueRefreshKey(value => value + 1);



  const userId = session?.principal?.subject;
  async function refreshDrafts() { setDrafts(sorted(await listDrafts(userId))); }



  useEffect(() => {
    let active = true;
    setDrafts([]); setForm(EMPTY); setEditingId(null);
    if (!userId) { setLoading(false); return () => { active = false; }; }
    setLoading(true);
    listDrafts(userId).then(items => { if (active) setDrafts(sorted(items)); })
      .catch(err => { if (active) setError(`Offline storage unavailable: ${err.message}`); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId]);

  useEffect(() => {
    const controller = new AbortController();
    setParcels([]);
    if (!session?.token) return () => controller.abort();
    setNotice('Loading authorized parcel list...');
    request('/api/v1/parcels', { signal: controller.signal })
      .then(async response => {
        if (response.status === 401 || response.status === 403) throw new Error(`Parcel access denied (${response.status}). Sign in with an authorized Field Verifier account.`);
        if (!response.ok) throw new Error(`Parcel request failed (${response.status})`);
        return response.json();
      })
      .then(items => { if (!controller.signal.aborted) { setParcels(Array.isArray(items) ? items : []); setNotice(items.length ? '' : 'No parcels available for this account.'); } })
      .catch(err => { if (!controller.signal.aborted) setNotice(err.message); });
    return () => controller.abort();
  }, [session?.token, request]);

  async function syncReadyEvidence() {
    if (!session?.token || session.expiresAt <= Date.now()) { setError('Sign in again before synchronizing.'); logout('Your session expired. Sign in again.'); return; }
    setSyncBusy(true); setError(''); setNotice('');
    let completed = 0;
    try {
      const ready = await listDrafts(userId);
      for (const record of ready.filter(item => item.status === READY)) {
        const issues = readinessIssues(record);
        if (issues.length) throw new Error(`Draft ${record.id}: ${issues.join(' ')}`);
        const result = await submitCompleteEvidence({ record, token: session.token, api: API });
        await removeQueuedEvidence(queueId(record.id), userId);
        await saveDraft({ ...record, status: 'server_submitted', server_evidence_id: result.id, updated_at: new Date().toISOString() }, userId);
        completed++;
      }
      await refreshDrafts(); refreshQueue();
      setNotice(completed ? `${completed} complete evidence record(s) submitted with photo.` : 'No ready records to submit.');
    } catch (err) {
      if (err.authFailure) logout('Your session expired. Sign in again.');
      setError(`Synchronization stopped after ${completed} completed record(s): ${err.message}. Remaining drafts are retained for retry.`);
      await refreshDrafts(); refreshQueue();
    } finally { setSyncBusy(false); }
  }

  useEffect(() => {

    if (!(form.photo instanceof Blob)) { setPhotoUrl(''); return; }

    const url = URL.createObjectURL(form.photo);

    setPhotoUrl(url);

    return () => URL.revokeObjectURL(url);

  }, [form.photo]);



  function captureLocation() {

    setError(''); setNotice('');

    if (!navigator.geolocation) { setError('Geolocation is unavailable.'); return; }

    if (!window.isSecureContext) { setError('GPS requires HTTPS or localhost. A plain HTTP LAN address is not secure.'); return; }

    setGpsBusy(true);

    navigator.geolocation.getCurrentPosition(

      position => {

        setForm(previous => ({ ...previous, latitude: String(position.coords.latitude), longitude: String(position.coords.longitude), accuracy_m: String(Math.round(position.coords.accuracy)), captured_at: new Date(position.timestamp).toISOString() }));

        setNotice('GPS captured. Check its accuracy before saving.');

        setGpsBusy(false);

      },

      e => { setError(`GPS capture failed: ${e.message}`); setGpsBusy(false); },

      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }

    );

  }



  async function persist(event) {

    event.preventDefault(); setError(''); setNotice('');

    if (!userId) { setError('Sign in as a Field Verifier before saving offline evidence.'); return; }

    if (!form.parcel_id || !form.observation.trim()) { setError('Select a parcel and enter an observation.'); return; }

    if (form.latitude !== '' && (!Number.isFinite(Number(form.latitude)) || Math.abs(Number(form.latitude)) > 90)) { setError('Invalid latitude.'); return; }

    if (form.longitude !== '' && (!Number.isFinite(Number(form.longitude)) || Math.abs(Number(form.longitude)) > 180)) { setError('Invalid longitude.'); return; }

    if (form.photo && (!form.photo.type.startsWith('image/') || form.photo.size > 8 * 1024 * 1024)) { setError('Photo must be an image of at most 8 MB.'); return; }

    setSaving(true);

    try {

      const previous = drafts.find(item => item.id === editingId);

      const now = new Date().toISOString();

      const record = { ...form, id: editingId || crypto.randomUUID(), observation: form.observation.trim(), created_at: previous?.created_at || now, updated_at: now, status: DRAFT };

      // If editing a ready record, invalidate its queued metadata before changing the draft.

      if (previous?.status === READY) await removeQueuedEvidence(queueId(previous.id), userId);

      await saveDraft(record, userId);

      await refreshDrafts();
      refreshQueue();

      setForm(EMPTY); setEditingId(null);

      setNotice(previous?.status === READY ? 'Updated locally. Previous queued metadata removed; mark ready again after review.' : 'Saved offline on this device. Nothing uploaded.');

    } catch (e) { setError(`Could not save draft: ${e.message}`); }

    finally { setSaving(false); }

  }



  async function toggleReady(record) {

    setError(''); setNotice(''); setBusyId(record.id);

    if (record.status === 'server_submitted') { setError('Submitted evidence cannot be changed locally.'); setBusyId(null); return; }
    const makeReady = record.status !== READY;

    const issues = makeReady ? readinessIssues(record) : [];

    if (issues.length) { setError(`Cannot mark ready: ${issues.join(' ')}`); setBusyId(null); return; }

    try {

      if (makeReady) {

        await enqueueEvidence({ client_record_id: queueId(record.id), parcel_id: record.parcel_id, observation: record.observation.trim(), latitude: Number(record.latitude), longitude: Number(record.longitude), captured_at: record.captured_at }, userId);

      } else {

        await removeQueuedEvidence(queueId(record.id), userId);

      }

      await saveDraft({ ...record, status: makeReady ? READY : DRAFT, updated_at: new Date().toISOString() }, userId);

      await refreshDrafts();
      refreshQueue();

      setNotice(makeReady ? 'Evidence metadata queued locally. Photo retained in the original draft. No server submission.' : 'Returned to draft; queued metadata removed.');

    } catch (e) {

      setError(`Queue update failed: ${e.message}. Review the record before retrying.`);

    } finally { setBusyId(null); }

  }



  function edit(record) {
    if (record.status === 'server_submitted') { setError('Submitted evidence cannot be edited.'); return; }

    setForm({ parcel_id: record.parcel_id, observation: record.observation, latitude: record.latitude ?? '', longitude: record.longitude ?? '', accuracy_m: record.accuracy_m ?? '', captured_at: record.captured_at ?? '', photo: record.photo || null });

    setEditingId(record.id); setError(''); setNotice('Editing a locally saved draft. Saving will require marking it ready again.');

    window.scrollTo({ top: 0, behavior: 'smooth' });

  }



  async function remove(record) {

    if (record.status === 'server_submitted') { setError('Submitted evidence cannot be deleted here.'); return; }
    if (!window.confirm('Delete this offline draft and its stored photo from this browser?')) return;

    setError(''); setBusyId(record.id);

    try {

      // Never leave ready-to-submit metadata behind after removing the original draft.

      await removeQueuedEvidence(queueId(record.id), userId);

      await deleteDraft(record.id, userId);

      await refreshDrafts();
      refreshQueue();

      if (editingId === record.id) { setEditingId(null); setForm(EMPTY); }

      setNotice('Local draft, photo and queued metadata deleted.');

    } catch (e) { setError(`Delete failed: ${e.message}`); }

    finally { setBusyId(null); }

  }



  const readyCount = drafts.filter(item => item.status === READY).length;
  const submittedCount = drafts.filter(item => item.status === 'server_submitted').length;

  return (

    <section className="field-workspace">

      <div className="field-heading">

        <div><h2>Field Verification</h2><p>Capture observations, GPS and photos. Prepare evidence offline for later submission.</p></div>

        <span className="field-pill">Offline drafts + manual secure sync</span>

      </div>

      <p className="field-warning">Drafts and photos remain in this browser's IndexedDB until you explicitly synchronize. Clearing site data may erase them. GPS requires HTTPS or localhost. Sync requires a Field Verifier login and a configured private photo store.</p>
      <FieldVerifierSession />
      <div className="field-actions"><button type="button" disabled={!session || syncBusy || !readyCount} onClick={syncReadyEvidence}>{syncBusy ? 'Submitting complete evidence...' : `Sync ${readyCount} ready record(s) with photos`}</button></div>

      {error && <p className="gis-error" role="alert">{error}</p>}

      {notice && <p className="field-notice" role="status">{notice}</p>}

      <div className="field-grid">

        <section className="field-card">

          <h3>{editingId ? 'Edit Offline Draft' : 'New Field Observation'}</h3>

          <form onSubmit={persist} className="field-form">

            <label htmlFor="field-parcel">Parcel</label>

            <select id="field-parcel" required value={form.parcel_id} onChange={e => setForm(previous => ({ ...previous, parcel_id: e.target.value }))}>

              <option value="">Select parcel</option>

              {form.parcel_id && !parcels.some(p => p.id === form.parcel_id) && <option value={form.parcel_id}>Saved parcel ({form.parcel_id})</option>}

              {parcels.map(p => <option key={p.id} value={p.id}>{p.external_id} — {p.village_code}</option>)}

            </select>

            <label htmlFor="field-observation">Field observation</label>

            <textarea id="field-observation" required rows={4} maxLength={3000} placeholder="Describe crop condition, observed issues, and evidence" value={form.observation} onChange={e => setForm(previous => ({ ...previous, observation: e.target.value }))} />

            <div className="field-inline">

              <button type="button" onClick={captureLocation} disabled={gpsBusy}>{gpsBusy ? 'Locating...' : 'Capture GPS'}</button>

              <span>{form.latitude !== '' && form.longitude !== '' ? `Lat ${Number(form.latitude).toFixed(6)}, Lon ${Number(form.longitude).toFixed(6)} (±${form.accuracy_m} m)` : 'No GPS captured'}</span>

            </div>

            <label htmlFor="field-photo">Evidence photo (max 8 MB)</label>

            <input id="field-photo" type="file" accept="image/*" capture="environment" onChange={e => {

              const file = e.target.files?.[0];

              if (!file) return;

              if (!file.type.startsWith('image/') || file.size > 8 * 1024 * 1024) { setError('Choose an image no larger than 8 MB.'); e.target.value = ''; return; }

              setError(''); setForm(previous => ({ ...previous, photo: file }));

            }} />

            {photoUrl && <div className="field-photo"><img src={photoUrl} alt="Selected field evidence preview" /><button type="button" onClick={() => setForm(previous => ({ ...previous, photo: null }))}>Remove photo</button></div>}

            <div className="field-actions">

              <button type="submit" disabled={!userId || saving || busyId !== null}>{saving ? 'Saving...' : editingId ? 'Update Offline Draft' : 'Save Offline Draft'}</button>

              {editingId && <button type="button" className="field-secondary" onClick={() => { setEditingId(null); setForm(EMPTY); }}>Cancel edit</button>}

            </div>

          </form>

        </section>

        <section className="field-card">

          <h3>Saved Records ({drafts.length})</h3>

          <p className="field-note">Ready locally: {readyCount}. Drafts: {drafts.length - readyCount - submittedCount}. Submitted: {submittedCount}.</p>

          {loading && <p>Loading drafts...</p>}

          {!loading && drafts.length === 0 && <p>No offline drafts saved on this device.</p>}

          <div className="field-drafts">

            {drafts.map(record => (

              <article key={record.id} className="field-draft">

                <div><strong>{parcels.find(p => p.id === record.parcel_id)?.external_id || record.parcel_id}</strong><small>{new Date(record.updated_at).toLocaleString()}</small></div>

                <p>{record.observation}</p>

                <small>{record.latitude !== '' && record.longitude !== '' ? `GPS: ${record.latitude}, ${record.longitude}` : 'GPS not captured'} · {record.photo ? 'Photo attached locally' : 'No photo'} · {record.status === READY ? 'Ready for manual photo + metadata sync' : record.status === 'server_submitted' ? 'Submitted to server' : 'Local draft — not submitted'}</small>

                <div className="field-actions">

                  {record.status !== 'server_submitted' && <button type="button" className="field-secondary" disabled={busyId !== null || saving || syncBusy} onClick={() => toggleReady(record)}>{busyId === record.id ? 'Working...' : record.status === READY ? 'Return to Draft' : 'Mark Ready'}</button>}

                  {record.status !== 'server_submitted' && <button type="button" disabled={busyId !== null || saving || syncBusy} onClick={() => edit(record)}>Edit</button>}

                  {record.status !== 'server_submitted' && <button type="button" className="field-danger" disabled={busyId !== null || saving || syncBusy} onClick={() => remove(record)}>Delete</button>}

                </div>

              </article>

            ))}

          </div>

        </section>

      </div>

      {userId && <FieldVerificationQueueSafe refreshKey={queueRefreshKey} userId={userId} />}
    </section>

  );

}

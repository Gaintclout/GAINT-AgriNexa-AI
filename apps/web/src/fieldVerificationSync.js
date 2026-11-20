/** AgriNexa Field Verification: optional offline sync helper.
 * Does not change existing UI or backend. Import explicitly when ready.
 * Photos are NOT transmitted by the Phase 3 JSON API; retain them locally.
 */
const STORE = 'queue';
export function offlineDatabaseName(prefix, userId) {
  if (typeof userId !== 'string' || !userId.trim()) throw new Error('Authenticated user is required for offline storage');
  return `${prefix}-${encodeURIComponent(userId.trim())}`;
}
function dbOpen(userId) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(offlineDatabaseName('agrinexa-field-sync-v2', userId), 1);
    req.onupgradeneeded = () => { if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE, { keyPath: 'client_record_id' }); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function transaction(userId, mode, action) {
  const db = await dbOpen(userId);
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const req = action(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(req?.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error('Transaction aborted'));
    });
  } finally { db.close(); }
}
export function validateEvidence(e) {
  if (!e || !/^[A-Za-z0-9_-]{1,100}$/.test(e.client_record_id || '')) throw new Error('Invalid client record ID');
  if (!/^[0-9a-fA-F-]{36}$/.test(e.parcel_id || '')) throw new Error('Invalid parcel ID');
  if (typeof e.observation !== 'string' || !e.observation.trim() || e.observation.length > 4000) throw new Error('Observation required (max 4000 characters)');
  if (!Number.isFinite(e.latitude) || Math.abs(e.latitude) > 90 || !Number.isFinite(e.longitude) || Math.abs(e.longitude) > 180) throw new Error('Invalid GPS coordinates');
  if (!e.captured_at || Number.isNaN(Date.parse(e.captured_at)) || Date.parse(e.captured_at) > Date.now()) throw new Error('Invalid capture timestamp');
  return {client_record_id:e.client_record_id, parcel_id:e.parcel_id, observation:e.observation, latitude:e.latitude, longitude:e.longitude, captured_at:e.captured_at};
}
export async function enqueueEvidence(e, userId) {
  const payload = validateEvidence(e);
  const entry = { ...payload, sync_status:'pending', attempts:0, last_error:null, updated_at:new Date().toISOString() };
  await transaction(userId, 'readwrite', store => store.put(entry));
  return entry;
}
export async function listQueuedEvidence(userId) { return await transaction(userId, 'readonly', store => store.getAll()) || []; }
export async function removeQueuedEvidence(id, userId) { await transaction(userId, 'readwrite', store => store.delete(id)); }
/** Legacy metadata-only sync is intentionally blocked to prevent incomplete submissions. */
export async function syncEvidenceQueue({token} = {}) {
  if (!token) throw new Error('Authentication required to synchronize');
  throw new Error('Metadata-only synchronization is disabled. Use the authenticated complete photo-evidence workflow.');
}

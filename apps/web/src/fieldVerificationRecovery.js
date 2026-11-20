import { enqueueEvidence, listQueuedEvidence, offlineDatabaseName } from './fieldVerificationSync';
import { auditLocalEvidence } from './fieldVerificationIntegrity';

const STORE = 'drafts';
const READY = 'ready_for_sync';
const queueId = id => String(id).replace(/-/g, '_');

function getDraft(id, userId) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(offlineDatabaseName('agrinexa-field-drafts-v2', userId));
    let missing = false;
    req.onupgradeneeded = () => { missing = true; req.transaction.abort(); };
    req.onerror = () => reject(new Error(missing ? 'Offline drafts database is missing.' : 'Cannot open offline drafts.'));
    req.onsuccess = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) { db.close(); reject(new Error('Draft store missing.')); return; }
      const tx = db.transaction(STORE, 'readonly');
      const request = tx.objectStore(STORE).get(id);
      tx.oncomplete = () => { db.close(); resolve(request.result || null); };
      tx.onerror = () => { db.close(); reject(tx.error || new Error('Cannot read draft.')); };
      tx.onabort = () => { db.close(); reject(tx.error || new Error('Draft read aborted.')); };
    };
  });
}

export function validateRecoveryDraft(draft) {
  if (!draft || draft.status !== READY) return 'Draft is missing or is no longer marked ready.';
  if (!/^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$/.test(draft.parcel_id || '')) return 'Parcel ID must be a valid UUID.';
  if (typeof draft.observation !== 'string' || !draft.observation.trim() || draft.observation.length > 3000) return 'Observation is invalid.';
  const lat = Number(draft.latitude), lon = Number(draft.longitude);
  if (draft.latitude === '' || draft.longitude === '' || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return 'GPS coordinates are invalid.';
  if (!draft.captured_at || !Number.isFinite(Date.parse(draft.captured_at)) || Date.parse(draft.captured_at) > Date.now()) return 'GPS capture timestamp is invalid.';
  if (!(draft.photo instanceof Blob) || !draft.photo.type.startsWith('image/') || !draft.photo.size || draft.photo.size > 8 * 1024 * 1024) return 'The original evidence photo is missing or invalid.';
  return null;
}

// Only two recoverable cases: a ready draft with missing queue metadata, or
// metadata that differs from its matching ready draft. Never deletes anything.
export async function recoverQueueMetadata(draftId, userId) {
  const id = queueId(draftId);
  const report = await auditLocalEvidence(userId);
  const issues = report.problems.filter(p => p.id === id);
  if (!issues.length || issues.some(p => !['missing_queue', 'mismatch'].includes(p.code))) {
    throw new Error('This record is not eligible for metadata recovery. Refresh the integrity check.');
  }
  const draft = await getDraft(draftId, userId);
  const problem = validateRecoveryDraft(draft);
  if (problem) throw new Error(problem);
  const queue = await listQueuedEvidence(userId);
  const current = queue.find(item => item.client_record_id === id);
  if (current?.sync_status === 'synced') throw new Error('Synced records cannot be changed by recovery.');
  if (issues.some(p => p.code === 'missing_queue') && current) throw new Error('Queue entry changed. Refresh before retrying.');
  if (issues.some(p => p.code === 'mismatch') && !current) throw new Error('Queue entry changed. Refresh before retrying.');
  await enqueueEvidence({
    client_record_id: id,
    parcel_id: draft.parcel_id,
    observation: draft.observation.trim(),
    latitude: Number(draft.latitude),
    longitude: Number(draft.longitude),
    captured_at: draft.captured_at
  }, userId);
  return { id, message: 'Queue metadata rebuilt from the original local draft. No photo or server data was changed.' };
}

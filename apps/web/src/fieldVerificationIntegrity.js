import { listQueuedEvidence, offlineDatabaseName } from './fieldVerificationSync';
const STORE = 'drafts';
const READY = 'ready_for_sync';
const queueId = id => String(id).replace(/-/g, '_');
export function inspectEvidenceIntegrity(drafts, queue) {
  const problems = [];
  const byId = new Map(drafts.map(d => [queueId(d.id), d]));
  const seen = new Set();
  for (const entry of queue) {
    const id = entry.client_record_id;
    if (seen.has(id)) problems.push({ id, code: 'duplicate', message: 'Duplicate queue identifier detected' });
    seen.add(id);
    const draft = byId.get(id);
    if (!draft) { problems.push({ id, code: 'orphan', message: 'Queued metadata has no matching offline draft' }); continue; }
    if (draft.status !== READY) problems.push({ id, code: 'not_ready', message: 'Queued metadata refers to a draft not marked ready' });
    if (!(draft.photo instanceof Blob) || !draft.photo.type.startsWith('image/') || draft.photo.size === 0 || draft.photo.size > 8 * 1024 * 1024) problems.push({ id, code: 'photo', message: 'Original evidence photo is missing or invalid' });
    if (draft.parcel_id !== entry.parcel_id || draft.observation?.trim() !== entry.observation?.trim() || Number(draft.latitude) !== Number(entry.latitude) || Number(draft.longitude) !== Number(entry.longitude) || draft.captured_at !== entry.captured_at) problems.push({ id, code: 'mismatch', message: 'Queued metadata differs from the original draft' });
  }
  for (const draft of drafts) {
    const id = queueId(draft.id);
    if (draft.status === READY && !seen.has(id)) problems.push({ id, code: 'missing_queue', message: 'Ready draft has no queue entry' });
  }
  return { checkedDrafts: drafts.length, checkedQueue: queue.length, problems, safe: problems.length === 0 };
}
function readDrafts(userId) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(offlineDatabaseName('agrinexa-field-drafts-v2', userId));
    let created = false;
    request.onupgradeneeded = () => { created = true; request.transaction.abort(); };
    request.onerror = () => reject(created ? new Error('Draft database does not exist on this device') : request.error);
    request.onsuccess = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) { db.close(); reject(new Error('Offline draft store is unavailable')); return; }
      const tx = db.transaction(STORE, 'readonly');
      const all = tx.objectStore(STORE).getAll();
      tx.oncomplete = () => { db.close(); resolve(all.result || []); };
      tx.onerror = () => { db.close(); reject(tx.error || new Error('Cannot inspect drafts')); };
      tx.onabort = () => { db.close(); reject(tx.error || new Error('Draft inspection interrupted')); };
    };
  });
}
export async function auditLocalEvidence(userId) {
  const [drafts, queue] = await Promise.all([readDrafts(userId), listQueuedEvidence(userId)]);
  return inspectEvidenceIntegrity(drafts, queue);
}

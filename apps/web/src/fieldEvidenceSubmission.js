/** Explicit, user-triggered two-step submission. Never stores the JWT. */
export async function submitCompleteEvidence({ record, token, api, fetchImpl = fetch }) {
  if (!token) throw new Error('Authentication required');
  if (!(record.photo instanceof Blob) || !record.photo.size) throw new Error('Evidence photo is required');
  const base = api.replace(/\/$/, '');
  const auth = { Authorization: `Bearer ${token}` };
  const metadata = {
    client_record_id: record.id.replace(/-/g, '_'), parcel_id: record.parcel_id,
    observation: record.observation.trim(), latitude: Number(record.latitude),
    longitude: Number(record.longitude), captured_at: record.captured_at,
  };
  async function check(response, action) {
    if (response.status === 401 || response.status === 403) {
      const err = new Error(`Access denied (${response.status}); sign in again`);
      err.authFailure = true; throw err;
    }
    if (!response.ok) {
      let detail = '';
      try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : ''; } catch {}
      throw new Error(`${action} failed (${response.status})${detail ? ': ' + detail : ''}`);
    }
    return response.json();
  }
  const metadataResponse = await fetchImpl(`${base}/api/v1/field-verification/evidence`, {
    method: 'POST', headers: { ...auth, 'Content-Type': 'application/json' }, body: JSON.stringify(metadata),
  });
  const evidence = await check(metadataResponse, 'Evidence metadata');
  if (!evidence?.id) throw new Error('Evidence response missing ID');
  if (evidence.status === 'submitted' && evidence.photo_sha256) {
    if (!globalThis.crypto?.subtle) throw new Error('Secure context required to verify previously submitted photo');
    const hash = await globalThis.crypto.subtle.digest('SHA-256', await record.photo.arrayBuffer());
    const localHash = [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2, '0')).join('');
    if (localHash !== evidence.photo_sha256) throw new Error('Server evidence already exists with a different photo');
    return evidence;
  }
  if (evidence.status !== 'pending_photo') throw new Error(`Unexpected evidence state: ${evidence.status}`);
  const form = new FormData();
  form.append('photo', record.photo, 'field-evidence');
  const photoResponse = await fetchImpl(`${base}/api/v1/field-verification/evidence/${encodeURIComponent(evidence.id)}/photo`, {
    method: 'POST', headers: auth, body: form,
  });
  const completed = await check(photoResponse, 'Photo upload');
  if (completed.status !== 'submitted' || !completed.photo_sha256) throw new Error('Server did not confirm complete evidence');
  return completed;
}

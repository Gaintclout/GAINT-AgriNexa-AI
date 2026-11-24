import React, { useCallback, useEffect, useState } from 'react';
import { listQueuedEvidence } from './fieldVerificationSync';
import { auditLocalEvidence } from './fieldVerificationIntegrity';
import { recoverQueueMetadata } from './fieldVerificationRecovery';

export default function FieldVerificationQueueManager({ userId }) {
  const [records, setRecords] = useState([]);
  const [audit, setAudit] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [repairing, setRepairing] = useState('');
  const [notice, setNotice] = useState('');
  const refresh = useCallback(async () => {
    setLoading(true); setError(''); setAudit(null);
    try {
      const [items, report] = await Promise.all([listQueuedEvidence(userId), auditLocalEvidence(userId)]);
      setRecords([...items].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')));
      setAudit(report);
    } catch (e) { setError(e?.message || 'Unable to inspect local evidence.'); }
    finally { setLoading(false); }
  }, [userId]);
  useEffect(() => { refresh(); }, [refresh]);
  async function recover(problem) {
    if (!window.confirm('Rebuild queued metadata from the saved local draft? No photos will be changed or uploaded.')) return;
    setRepairing(problem.id); setError(''); setNotice('');
    try {
      const draftId = problem.id.replace(/_/g, '-');
      const result = await recoverQueueMetadata(draftId, userId);
      setNotice(result.message);
      await refresh();
    } catch (e) { setError(e?.message || 'Metadata recovery failed.'); }
    finally { setRepairing(''); }
  }
  const pending = records.filter(r => r.sync_status === 'pending' && !r.attempts).length;
  const retryPending = records.filter(r => r.sync_status === 'pending' && r.attempts > 0).length;
  const synced = records.filter(r => r.sync_status === 'synced').length;
  return (
    <section className="field-card field-queue-panel" aria-label="Offline evidence queue">
      <h3>Offline evidence queue</h3>
      <p className="field-note">Review locally stored evidence and check its integrity. Metadata recovery requires your confirmation. This panel does not upload photos or submit evidence.</p>
      <div className="field-queue-summary">

        <div className="field-queue-stat queue-pending">
          <span>Pending</span>
          <strong>{loading ? '...' : pending}</strong>
          <small>Waiting for sync</small>
        </div>

        <div className="field-queue-stat queue-retry">
          <span>Retry pending</span>
          <strong>{loading ? '...' : retryPending}</strong>
          <small>Previous attempts recorded</small>
        </div>

        <div className="field-queue-stat queue-synced">
          <span>Synced</span>
          <strong>{loading ? '...' : synced}</strong>
          <small>Synced queue entries</small>
        </div>

        <div className="field-queue-stat queue-total">
          <span>Total records</span>
          <strong>{loading ? '...' : records.length}</strong>
          <small>Local queue entries</small>
        </div>

      </div>
      <div className="field-actions"><button type="button" className="field-secondary" disabled={loading} onClick={refresh}>{loading ? 'Checking...' : 'Refresh & check integrity'}</button></div>
      {error && <p className="gis-error" role="alert">{error}</p>}
      {notice && <p className="field-note" role="status">{notice}</p>}
      {audit && <div className={`field-integrity-result ${audit.safe ? "integrity-passed" : "integrity-warning"}`} role="status">
        <strong>{audit.safe ? 'Integrity check passed' : `${audit.problems.length} integrity issue(s) found`}</strong>
        <p>Checked {audit.checkedDrafts} drafts and {audit.checkedQueue} queue entries.</p>
        {!audit.safe && <p>Do not synchronize these records until the issues are resolved. No automatic repair has been attempted.</p>}
        {audit.problems.map((problem, i) => <div key={`${problem.id}-${problem.code}-${i}`} className="field-draft"><p className="gis-error">{problem.id}: {problem.message}</p>{['missing_queue', 'mismatch'].includes(problem.code) && !audit.problems.some(p => p.id === problem.id && !['missing_queue', 'mismatch'].includes(p.code)) && <button type="button" className="field-secondary" disabled={Boolean(repairing)} onClick={() => recover(problem)}>{repairing === problem.id ? 'Recovering...' : 'Recover metadata'}</button>}</div>)}
      </div>}
      {!loading && !error && records.length === 0 && <p className="field-note">No queued records on this device.</p>}
      <div className="field-drafts">{records.map(record => <article className="field-draft field-queue-record" key={record.client_record_id}>
        <div><strong>{record.sync_status === 'synced' ? 'Synced' : record.attempts > 0 ? 'Retry pending' : 'Pending'}</strong><small>{record.client_record_id}</small></div>
        <p>{record.observation}</p><small>Land record: {record.parcel_id} | Attempts: {record.attempts || 0}</small>
        {record.last_error && <p className="gis-error">Last error: {record.last_error}</p>}
        <div className="field-actions"><button type="button" className="field-secondary" onClick={() => setSelected(v => v === record.client_record_id ? null : record.client_record_id)}>{selected === record.client_record_id ? 'Hide details' : 'View details'}</button></div>
        {selected === record.client_record_id && <div className="field-note"><p>Latitude: {record.latitude}</p><p>Longitude: {record.longitude}</p><p>Captured: {record.captured_at}</p><p>Updated: {record.updated_at || 'Unknown'}</p><p>Photo upload: Available through explicit Field Verification sync</p></div>}
      </article>)}</div>
    </section>
  );
}

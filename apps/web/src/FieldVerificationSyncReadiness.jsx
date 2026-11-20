import React, { useState } from 'react';
import { auditLocalEvidence } from './fieldVerificationIntegrity';
import { listQueuedEvidence } from './fieldVerificationSync';

export default function FieldVerificationSyncReadiness({ refreshKey, userId }) {
  const [checking, setChecking] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  async function checkReadiness() {
    setChecking(true);
    setError('');
    setReport(null);

    try {
      const [integrity, queue] = await Promise.all([
        auditLocalEvidence(userId),
        listQueuedEvidence(userId)
      ]);

      const ready = queue.filter(
        item => item.sync_status === 'pending'
      ).length;

      const blocked = queue.filter(
        item => item.sync_status !== 'pending'
      ).length;

      setReport({
        integrity,
        ready,
        blocked,
        total: queue.length,
        checkedAt: new Date().toLocaleString(),
        refreshKey
      });
    } catch (err) {
      setError(
        err?.message || 'Could not inspect offline evidence.'
      );
    } finally {
      setChecking(false);
    }
  }

  const stale = report && report.refreshKey !== refreshKey;

  return (
    <section
      className="field-card"
      style={{ marginTop: 16 }}
      aria-label="Synchronization readiness"
    >
      <h3>Evidence Synchronization Readiness</h3>

      <p className="field-note">
        Check whether local evidence is prepared for future
        synchronization. This check never uploads data.
      </p>

      <div className="field-actions">
        <button
          type="button"
          disabled={checking}
          onClick={checkReadiness}
        >
          {checking ? 'Checking...' : 'Check Readiness'}
        </button>
      </div>

      {error && (
        <p className="gis-error" role="alert">
          {error}
        </p>
      )}

      {report && (
        <div aria-live="polite">
          {stale && (
            <p className="field-warning">
              Local evidence has changed. Run the check again.
            </p>
          )}

          <p>Queued records: <strong>{report.total}</strong></p>
          <p>Pending records: <strong>{report.ready}</strong></p>
          <p>Other queue statuses: <strong>{report.blocked}</strong></p>
          <p>
            Integrity issues:
            <strong> {report.integrity.problems.length}</strong>
          </p>

          {report.integrity.problems.map((problem, index) => (
            <p className="gis-error" key={`${problem.id}-${index}`}>
              {problem.message} — {problem.id}
            </p>
          ))}

          <p className="field-note">
            Last checked: {report.checkedAt}
          </p>
        </div>
      )}

      <hr />

      <h4>Backend activation requirements</h4>

      <p className="field-note">
        The following requirements have not yet been verified:
      </p>

      <ul>
        <li>Authenticated Field Verifier session and permissions</li>
        <li>PostgreSQL migration applied successfully</li>
        <li>Backend evidence API contract verified</li>
        <li>Photo upload and evidence linkage implemented</li>
        <li>Duplicate-safe server submission verified</li>
        <li>Phase 4H browser acceptance completed</li>
      </ul>

      <p className="field-warning">
        Server synchronization is disabled. A successful local
        integrity check does not authorize submission.
      </p>

      <button type="button" disabled>
        Submit Evidence — Not Available Yet
      </button>
    </section>
  );
}

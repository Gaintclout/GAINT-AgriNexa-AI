
import React, { useEffect, useState } from 'react';

import {
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  ClipboardCheck,
  Search,
  MapPin,
  Image,
  FileText,
  History,
  Eye
} from 'lucide-react';

import { useAuth } from './AuthContext.jsx';
import {
  decisionLabel,
  validateReview
} from './reviewUtils.js';

const STATUS_LABELS = {
  submitted: 'Pending review',
  approved: 'Approved',
  rejected: 'Rejected',
  correction_requested: 'Correction requested'
};

const statusLabel = status =>
  STATUS_LABELS[status] || status || 'Unknown';

async function json(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      typeof data?.detail === 'string'
        ? data.detail
        : `Request failed (${response.status})`
    );
  }

  return data;
}

export default function OfficerReview() {
  const { session, request } = useAuth();

  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [parcel, setParcel] = useState(null);
  const [audit, setAudit] = useState([]);
  const [photoUrl, setPhotoUrl] = useState('');

  const [decision, setDecision] = useState('approved');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const [loading, setLoading] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const allowed = ['officer', 'admin'].includes(
    session?.principal.role
  );

  async function load() {
    if (!allowed) return;

    setError('');
    setLoading(true);

    try {
      const records = await request(
        '/api/v1/field-verification/evidence?limit=100&offset=0'
      ).then(json);

      setItems(records);

    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [allowed, request]);

  // Existing authorized photo retrieval
  useEffect(() => {
    let active = true;
    let url = '';

    setPhotoUrl('');

    if (!selected?.photo_sha256) return;

    request(
      `/api/v1/field-verification/evidence/${encodeURIComponent(selected.id)}/photo`
    )
      .then(r => {
        if (!r.ok) {
          throw new Error(`Photo unavailable (${r.status})`);
        }

        return r.blob();
      })
      .then(blob => {
        if (active) {
          url = URL.createObjectURL(blob);
          setPhotoUrl(url);
        }
      })
      .catch(e => {
        if (active) setError(e.message);
      });

    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };

  }, [
    selected?.id,
    selected?.photo_sha256,
    request
  ]);

  async function inspect(record) {
    setSelected(record);
    setParcel(null);
    setAudit([]);
    setError('');
    setNotice('');
    setInspecting(true);

    try {
      const [p, a] = await Promise.all([
        request(
          '/api/v1/parcels/' +
          encodeURIComponent(record.parcel_id)
        ).then(json),

        request(
          `/api/v1/field-verification/evidence/${encodeURIComponent(record.id)}/audit`
        ).then(json)
      ]);

      setParcel(p);
      setAudit(a);

    } catch (e) {
      setError(e.message);
    } finally {
      setInspecting(false);
    }
  }

  async function submit(event) {
    event.preventDefault();

    const problem = validateReview(decision, note);

    if (problem) {
      setError(problem);
      return;
    }

    if (!selected || selected.status !== 'submitted') {
      setError('Only submitted evidence can be reviewed.');
      return;
    }

    if (!window.confirm(
      `${decisionLabel(decision)} this evidence?`
    )) return;

    setBusy(true);
    setError('');
    setNotice('');

    try {
      const updated = await request(
        `/api/v1/field-verification/evidence/${encodeURIComponent(selected.id)}/review`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            decision,
            note: note.trim()
          })
        }
      ).then(json);

      setSelected(updated);

      setItems(values =>
        values.map(item =>
          item.id === updated.id ? updated : item
        )
      );

      setAudit(
        await request(
          `/api/v1/field-verification/evidence/${encodeURIComponent(updated.id)}/audit`
        ).then(json)
      );

      setNotice(
        `Decision recorded: ${decisionLabel(updated.status)}.`
      );

      setNote('');

    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const summary = [
    {
      label: 'Pending review',
      status: 'submitted',
      icon: Clock,
      theme: 'pending'
    },
    {
      label: 'Approved',
      status: 'approved',
      icon: CheckCircle,
      theme: 'approved'
    },
    {
      label: 'Rejected',
      status: 'rejected',
      icon: XCircle,
      theme: 'rejected'
    },
    {
      label: 'Correction requested',
      status: 'correction_requested',
      icon: ClipboardCheck,
      theme: 'correction'
    }
  ];

  const term = search.trim().toLowerCase();

  const filteredItems = items.filter(item => {
    const matchesStatus =
      statusFilter === 'all' ||
      item.status === statusFilter;

    const matchesSearch = [
      item.id,
      item.parcel_id,
      item.observation,
      statusLabel(item.status)
    ].some(value =>
      String(value ?? '').toLowerCase().includes(term)
    );

    return matchesStatus && matchesSearch;
  });

  if (!session) {
    return (
      <section className="field-workspace">
        <div className="field-card">
          <h2>Officer Evidence Review</h2>
          <p>Sign in as an Officer or Admin.</p>
        </div>
      </section>
    );
  }

  if (!allowed) {
    return (
      <section className="field-workspace">
        <div className="field-card">
          <h2>Officer Evidence Review</h2>
          <p className="gis-error">
            Your account is not authorized to review evidence.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="field-workspace officer-workspace">

      <div className="field-heading">
        <div>
          <h2>Officer Evidence Review</h2>
          <p>
            Inspect field evidence and record review decisions.
          </p>
        </div>

        <button
          type="button"
          className="officer-secondary"
          disabled={loading || busy || inspecting}
          onClick={load}
        >
          <RefreshCw size={17} />
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="officer-summary-grid">
        {summary.map(item => {
          const Icon = item.icon;

          return (
            <button
              type="button"
              key={item.status}
              className={`officer-summary-card officer-${item.theme}`}
              aria-pressed={statusFilter === item.status}
              disabled={loading}
              onClick={() =>
                setStatusFilter(current =>
                  current === item.status
                    ? 'all'
                    : item.status
                )
              }
            >
              <div>
                <Icon size={22} />
                <span>{item.label}</span>
              </div>

              <strong>
                {loading
                  ? '...'
                  : items.filter(
                      record => record.status === item.status
                    ).length}
              </strong>

              <small>View records</small>
            </button>
          );
        })}
      </div>

      <p className="officer-count-note">
        Summary based on the currently loaded evidence records.
      </p>

      {error && (
        <p className="gis-error" role="alert">
          {error}
        </p>
      )}

      {notice && (
        <p className="field-notice" role="status">
          {notice}
        </p>
      )}

      <div className="officer-review-grid">

        <section className="field-card officer-list">

          <div className="officer-section-heading">
            <h3>Evidence records</h3>
            <span>{filteredItems.length} records</span>
          </div>

          <div className="officer-filters">

            <div className="officer-search">
              <Search size={19} />

              <input
                type="search"
                aria-label="Search evidence"
                placeholder="Search evidence..."
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>

            <select
              aria-label="Filter by review status"
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="submitted">Pending review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="correction_requested">
                Correction requested
              </option>
            </select>

          </div>

          {loading && (
            <p className="field-note" role="status">
              Loading evidence records...
            </p>
          )}

          {!loading && !error && filteredItems.length === 0 && (
            <div className="officer-empty">
              <FileText size={36} />
              <h4>No evidence records found</h4>
              <p>Try changing the search or status filter.</p>
            </div>
          )}

          <div className="field-drafts">

            {filteredItems.map(item => (
              <article
                key={item.id}
                className={`field-draft officer-record ${
                  selected?.id === item.id
                    ? 'officer-record-selected'
                    : ''
                }`}
              >

                <div className="officer-record-heading">
                  <span
                    className={`officer-status status-${item.status}`}
                  >
                    {statusLabel(item.status)}
                  </span>
                </div>

                <p className="officer-observation">
                  {item.observation}
                </p>

                <small>
                  Land record: {item.parcel_id}
                </small>

                <small>
                  Captured: {
                    new Date(item.captured_at).toLocaleString()
                  }
                </small>

                <button
                  type="button"
                  disabled={busy || inspecting}
                  onClick={() => inspect(item)}
                >
                  <Eye size={17} />
                  {selected?.id === item.id
                    ? 'Inspect again'
                    : 'Inspect evidence'}
                </button>

              </article>
            ))}

          </div>

        </section>

        <section className="field-card officer-details">

          <h3>Review details</h3>

          {!selected && (
            <div className="officer-empty">
              <ClipboardCheck size={42} />
              <h4>Select an evidence record</h4>
              <p>
                Inspect a record to view its details,
                photograph and review history.
              </p>
            </div>
          )}

          {selected && (
            <>

              <span
                className={`officer-status status-${selected.status}`}
              >
                {statusLabel(selected.status)}
              </span>

              <div className="officer-detail-grid">

                <div>
                  <span>Land ID</span>
                  <strong>
                    {parcel?.external_id || selected.parcel_id}
                  </strong>
                </div>

                <div>
                  <span>Village code</span>
                  <strong>
                    {parcel?.village_code ||
                      (inspecting ? 'Loading...' : 'Unavailable')}
                  </strong>
                </div>

              </div>

              <div className="officer-information-card">

                <h4>
                  <MapPin size={19} />
                  GPS information
                </h4>

                <dl>
                  <dt>Latitude</dt>
                  <dd>{selected.latitude}</dd>

                  <dt>Longitude</dt>
                  <dd>{selected.longitude}</dd>

                  <dt>Captured at</dt>
                  <dd>
                    {new Date(
                      selected.captured_at
                    ).toLocaleString()}
                  </dd>
                </dl>

              </div>

              <div className="officer-information-card">
                <h4>
                  <FileText size={19} />
                  Field observation
                </h4>

                <p>{selected.observation}</p>
              </div>

              <div className="officer-information-card">

                <h4>
                  <Image size={19} />
                  Evidence photograph
                </h4>

                {photoUrl ? (
                  <div className="field-photo">
                    <img
                      src={photoUrl}
                      alt="Authorized field evidence"
                    />
                  </div>
                ) : (
                  <div className="officer-photo-empty">
                    <Image size={36} />
                    <p>
                      {selected.photo_sha256
                        ? 'Photo preview not available yet.'
                        : 'No evidence photo recorded.'}
                    </p>
                  </div>
                )}

              </div>

              {selected.status === 'submitted' && (
                <div className="officer-decision-card">

                  <h4>Record decision</h4>

                  <form
                    className="field-form"
                    onSubmit={submit}
                  >

                    <label htmlFor="officer-decision">
                      Review decision
                    </label>

                    <select
                      id="officer-decision"
                      value={decision}
                      onChange={e =>
                        setDecision(e.target.value)
                      }
                    >
                      <option value="approved">Approve</option>
                      <option value="rejected">Reject</option>
                      <option value="correction_requested">
                        Request correction
                      </option>
                    </select>

                    <label htmlFor="officer-note">
                      Review note
                    </label>

                    <textarea
                      id="officer-note"
                      rows={4}
                      maxLength={2000}
                      placeholder="Enter review comments..."
                      value={note}
                      onChange={e => setNote(e.target.value)}
                    />

                    <small className="officer-character-count">
                      {note.length} / 2000 characters
                    </small>

                    <button
                      type="submit"
                      disabled={busy || inspecting}
                    >
                      <CheckCircle size={18} />
                      {busy ? 'Saving...' : 'Record decision'}
                    </button>

                  </form>

                </div>
              )}

              <div className="officer-audit">

                <h4>
                  <History size={20} />
                  Audit history
                </h4>

                {inspecting && <p>Loading audit history...</p>}

                {!inspecting && audit.length === 0 && (
                  <p>No audit entries loaded.</p>
                )}

                {audit.map(entry => (
                  <div
                    className="officer-audit-entry"
                    key={entry.id}
                  >
                    <strong>{entry.action}</strong>

                    <small>
                      {new Date(
                        entry.created_at
                      ).toLocaleString()}
                    </small>

                    <p>Actor: {entry.actor_id}</p>

                    {entry.note && (
                      <p>Note: {entry.note}</p>
                    )}
                  </div>
                ))}

              </div>

            </>
          )}

        </section>

      </div>

    </section>
  );
}

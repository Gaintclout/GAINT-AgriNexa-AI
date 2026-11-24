
import React, {
  useCallback,
  useEffect,
  useState
} from 'react';

import ParcelMap from './ParcelMap.jsx';
import { useAuth } from './AuthContext.jsx';
import {
  ownershipLabel,
  validateOwnerSelection
} from './ownershipUtils.js';

const EMPTY = {
  external_id: '',
  village_code: '',
  area_hectares: ''
};

const PAGE_SIZE = 50;

async function parseResponse(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = data?.detail;

    const message = Array.isArray(detail)
      ? detail.map(item => item.msg || 'Invalid field').join('; ')
      : typeof detail === 'string'
        ? detail
        : `Request failed (${response.status})`;

    throw new Error(message);
  }

  return data;
}

function validateParcelForm(form) {
  const externalId = form.external_id.trim();
  const villageCode = form.village_code.trim();
  const areaText = String(form.area_hectares).trim();
  const area = Number(areaText);

  if (!externalId || externalId.length > 100) {
    return 'Enter a valid parcel ID (maximum 100 characters).';
  }

  if (!villageCode) {
    return 'Select a village.';
  }

  if (!areaText || !Number.isFinite(area) || area <= 0) {
    return 'Enter an area greater than zero.';
  }

  if (area > 99999999.9999) {
    return 'Parcel area exceeds the supported maximum.';
  }

  const decimals = areaText.split('.')[1];

  if (decimals && decimals.length > 4) {
    return 'Area can contain a maximum of four decimal places.';
  }

  return '';
}

function parcelPayload(form) {
  return {
    external_id: form.external_id.trim(),
    village_code: form.village_code.trim(),
    area_hectares: Number(form.area_hectares)
  };
}

export default function ParcelRegistry() {
  const { session, request } = useAuth();

  const role = session?.principal?.role;

  const canEdit = ['admin', 'gis_operator'].includes(role);

  const [parcels, setParcels] = useState([]);
  const [villages, setVillages] = useState([]);
  const [farmers, setFarmers] = useState([]);

  const [ownerDrafts, setOwnerDrafts] = useState({});
  const [ownerBusy, setOwnerBusy] = useState('');

  const [form, setForm] = useState(EMPTY);
  const [formError, setFormError] = useState('');
  const [saving, setSaving] = useState(false);

  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');

  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const [selected, setSelected] = useState(null);

  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState(EMPTY);
  const [editError, setEditError] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const refresh = useCallback(async (
    signal,
    targetPage = page,
    searchTerm = appliedSearch
  ) => {
    if (!session) return;

    const query = new URLSearchParams({
      limit: String(PAGE_SIZE + 1),
      offset: String(targetPage * PAGE_SIZE)
    });

    if (searchTerm) {
      query.set('search', searchTerm);
    }

    const parcelData = await request(
      `/api/v1/parcels?${query}`,
      { signal }
    ).then(parseResponse);

    const villageData = role === 'farmer'
      ? []
      : await request('/api/v1/villages', { signal })
          .then(parseResponse);

    const farmerData = canEdit
      ? await request('/api/v1/users/farmers', { signal })
          .then(parseResponse)
      : [];

    if (signal?.aborted) return;

    const pageItems = Array.isArray(parcelData)
      ? parcelData
      : [];

    const visibleItems = pageItems.slice(0, PAGE_SIZE);

    setParcels(visibleItems);
    setHasMore(pageItems.length > PAGE_SIZE);

    setVillages(
      Array.isArray(villageData) ? villageData : []
    );

    setFarmers(
      Array.isArray(farmerData) ? farmerData : []
    );

    setOwnerDrafts(
      Object.fromEntries(
        visibleItems.map(parcel => [
          parcel.id,
          parcel.farmer_id || ''
        ])
      )
    );
  }, [session, request, role, canEdit, page, appliedSearch]);

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError('');

    refresh(controller.signal)
      .catch(err => {
        if (err.name !== 'AbortError' && !controller.signal.aborted) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [refresh]);

  async function manualRefresh() {
    setError('');
    setLoading(true);

    try {
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function createParcel(event) {
    event.preventDefault();

    setFormError('');
    setSuccess('');

    const problem = validateParcelForm(form);

    if (problem) {
      setFormError(problem);
      return;
    }

    setSaving(true);

    try {
      const created = await request('/api/v1/parcels', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(parcelPayload(form))
      }).then(parseResponse);

      setForm({ ...EMPTY });
      setSelected(created);
      setSuccess('Parcel registered successfully.');

      setSearch('');
      setAppliedSearch('');
      setPage(0);

      try {
        await refresh(undefined, 0, '');
      } catch (err) {
        setError(
          'Parcel saved, but the list could not be refreshed: ' +
          err.message
        );
      }
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function viewParcel(id) {
    setError('');

    try {
      const parcel = await request(
        `/api/v1/parcels/${encodeURIComponent(id)}`
      ).then(parseResponse);

      setSelected(parcel);
    } catch (err) {
      setError(err.message);
    }
  }

  async function assignOwner(parcel) {
    const farmerId = ownerDrafts[parcel.id] || null;

    const problem = validateOwnerSelection(
      farmerId,
      farmers
    );

    if (problem) {
      setError(problem);
      return;
    }

    const label = ownershipLabel(farmerId, farmers);

    if (!window.confirm(
      `Change ownership of ${parcel.external_id} to ${label}?`
    )) {
      return;
    }

    setOwnerBusy(parcel.id);
    setError('');
    setSuccess('');

    try {
      const updated = await request(
        `/api/v1/parcels/${encodeURIComponent(parcel.id)}/owner`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            farmer_id: farmerId
          })
        }
      ).then(parseResponse);

      setParcels(items =>
        items.map(item =>
          item.id === updated.id ? updated : item
        )
      );

      setOwnerDrafts(values => ({
        ...values,
        [updated.id]: updated.farmer_id || ''
      }));

      setSelected(current =>
        current?.id === updated.id ? updated : current
      );

      setSuccess(
        `Ownership updated for ${parcel.external_id}.`
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setOwnerBusy('');
    }
  }

  function startEditing(parcel) {
    if (!canEdit) return;

    setEditing(parcel);
    setEditForm({
      external_id: parcel.external_id || '',
      village_code: parcel.village_code || '',
      area_hectares: String(parcel.area_hectares ?? '')
    });

    setEditError('');
    setError('');
    setSuccess('');
  }

  function cancelEditing() {
    if (editSaving) return;

    setEditing(null);
    setEditForm({ ...EMPTY });
    setEditError('');
  }

  async function saveParcel(event) {
    event.preventDefault();

    if (!canEdit || !editing || editSaving) return;

    setEditError('');
    setSuccess('');

    const problem = validateParcelForm(editForm);

    if (problem) {
      setEditError(problem);
      return;
    }

    setEditSaving(true);

    try {
      const updated = await request(
        `/api/v1/parcels/${encodeURIComponent(editing.id)}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(parcelPayload(editForm))
        }
      ).then(parseResponse);

      setParcels(items =>
        items.map(item =>
          item.id === updated.id ? updated : item
        )
      );

      setSelected(current =>
        current?.id === updated.id ? updated : current
      );

      setEditing(null);
      setEditForm({ ...EMPTY });

      setSuccess(
        `Parcel ${updated.external_id} updated successfully.`
      );

      try {
        await refresh();
      } catch (err) {
        setError(
          'Parcel updated, but the list could not be refreshed: ' +
          err.message
        );
      }
    } catch (err) {
      setEditError(err.message);
    } finally {
      setEditSaving(false);
    }
  }

  // Farmer-friendly read-only land interface
  if (session && role === 'farmer') {
    return (
      <section className="farmer-land-page">

        <div className="farmer-land-heading">
          <div>
            <h1>My Land</h1>
            <p>View your agricultural land records.</p>
          </div>

          <button
            type="button"
            className="farmer-land-secondary"
            disabled={loading}
            onClick={manualRefresh}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        <div className="farmer-land-summary">
          <span>My land records</span>
          <strong>{loading ? '...' : parcels.length}</strong>
          <p>
            Records on this page
            {hasMore ? ' - More records available' : ''}
          </p>
        </div>

        {error && (
          <div className="gis-error" role="alert">
            {error}
          </div>
        )}

        <section className="farmer-land-section">
          <h2>Find your land</h2>

          <form
            className="farmer-land-search"
            onSubmit={event => {
              event.preventDefault();
              setSelected(null);
              setPage(0);
              setAppliedSearch(search.trim());
            }}
          >
            <label htmlFor="farmer-land-search">
              Search land records
            </label>

            <input
              id="farmer-land-search"
              placeholder="Enter land ID or village code"
              maxLength={100}
              value={search}
              onChange={event =>
                setSearch(event.target.value)
              }
            />

            <div className="farmer-land-actions">
              <button
                type="submit"
                className="farmer-land-primary"
                disabled={loading}
              >
                Search
              </button>

              <button
                type="button"
                className="farmer-land-secondary"
                disabled={loading}
                onClick={() => {
                  setSearch('');
                  setSelected(null);
                  setPage(0);
                  setAppliedSearch('');
                }}
              >
                Clear
              </button>
            </div>
          </form>
        </section>

        <div className="farmer-land-heading">
          <h2>Land records</h2>
        </div>

        {loading && (
          <div
            className="farmer-land-section"
            role="status"
          >
            Loading your land records...
          </div>
        )}

        {!loading && !error && parcels.length === 0 && (
          <div className="farmer-land-empty">
            <h3>No land records found</h3>
            <p>
              {appliedSearch
                ? 'Try searching with a different land ID or village code.'
                : 'No land records are currently assigned to your account.'}
            </p>
          </div>
        )}

        {!loading && !error && (
          <div className="farmer-land-grid">
            {parcels.map(parcel => (
              <article
                key={parcel.id}
                className="farmer-land-card"
              >
                <div className="farmer-land-card-top">
                  <div>
                    <span className="farmer-land-caption">
                      Land ID
                    </span>
                    <h3>{parcel.external_id}</h3>
                  </div>

                  <span className="farmer-land-badge">
                    {parcel.farmer_id
                      ? 'Assigned to you'
                      : 'Unassigned'}
                  </span>
                </div>

                <dl className="farmer-land-fields">
                  <div>
                    <dt>Village code</dt>
                    <dd>{parcel.village_code}</dd>
                  </div>

                  <div>
                    <dt>Land area</dt>
                    <dd>
                      {parcel.area_hectares != null &&
                       Number.isFinite(Number(parcel.area_hectares))
                        ? `${(Number(parcel.area_hectares) * 2.47105381).toFixed(2)} acres`
                        : 'Unavailable'}
                    </dd>
                    <small>
                      {parcel.area_hectares ?? 'Unavailable'} hectares
                    </small>
                  </div>
                </dl>

                <button
                  type="button"
                  className="farmer-land-primary"
                  onClick={() => viewParcel(parcel.id)}
                >
                  View land details
                </button>

                {selected?.id === parcel.id && (
                  <div className="farmer-land-detail">
                    <div className="farmer-land-heading">
                      <h3>Land details</h3>

                      <button
                        type="button"
                        className="farmer-land-secondary"
                        onClick={() => setSelected(null)}
                      >
                        Close
                      </button>
                    </div>

                    <dl className="farmer-land-fields">
                      <div>
                        <dt>Land ID</dt>
                        <dd>{selected.external_id}</dd>
                      </div>

                      <div>
                        <dt>Village code</dt>
                        <dd>{selected.village_code}</dd>
                      </div>

                      <div>
                        <dt>Area in hectares</dt>
                        <dd>{selected.area_hectares}</dd>
                      </div>

                      <div>
                        <dt>Ownership</dt>
                        <dd>
                          {selected.farmer_id
                            ? 'Assigned to you'
                            : 'Unassigned'}
                        </dd>
                      </div>

                      <div>
                        <dt>Record ID</dt>
                        <dd>{selected.id}</dd>
                      </div>

                      <div>
                        <dt>Record created</dt>
                        <dd>
                          {selected.created_at || 'Unavailable'}
                        </dd>
                      </div>
                    </dl>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}

        <div className="farmer-land-pagination">
          <button
            type="button"
            className="farmer-land-secondary"
            disabled={page === 0 || loading}
            onClick={() => {
              setSelected(null);
              setPage(value => Math.max(0, value - 1));
            }}
          >
            Previous
          </button>

          <span>Page {page + 1}</span>

          <button
            type="button"
            className="farmer-land-secondary"
            disabled={!hasMore || loading}
            onClick={() => {
              setSelected(null);
              setPage(value => value + 1);
            }}
          >
            Next
          </button>
        </div>

        <ParcelMap />

      </section>
    );
  }

  if (!session) {
    return (
      <div className="registry">
        <section className="registry-card">
          <h2>Parcel Registry</h2>
          <p>Sign in to access parcels allowed for your role.</p>
        </section>
      </div>
    );
  }

  return (
    <div className="registry">
      <div className="registry-heading">
        <div>
          <h2>Parcel Registry</h2>
          <p>
            {canEdit
              ? 'Manage agricultural parcels and village records.'
              : role === 'farmer'
                ? 'View parcels assigned to your account.'
                : 'View parcels permitted for your role.'}
          </p>
        </div>

        <button
          type="button"
          disabled={loading}
          onClick={manualRefresh}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && (
        <p className="gis-error" role="alert">
          {error}
        </p>
      )}

      {success && (
        <p className="registry-success" role="status">
          {success}
        </p>
      )}

      <div className="registry-grid">
        {canEdit && (
          <section className="registry-card">
            <h3>Register Parcel</h3>

            <form
              onSubmit={createParcel}
              className="registry-form"
            >
              <label htmlFor="parcel-id">
                Parcel ID
              </label>

              <input
                id="parcel-id"
                maxLength={100}
                required
                placeholder="Enter parcel reference"
                value={form.external_id}
                onChange={event =>
                  setForm({
                    ...form,
                    external_id: event.target.value
                  })
                }
              />

              <label htmlFor="parcel-village">
                Village
              </label>

              <select
                id="parcel-village"
                required
                disabled={!villages.length}
                value={form.village_code}
                onChange={event =>
                  setForm({
                    ...form,
                    village_code: event.target.value
                  })
                }
              >
                <option value="">
                  {villages.length
                    ? 'Select village'
                    : 'No villages available'}
                </option>

                {villages.map(village => (
                  <option
                    key={village.code}
                    value={village.code}
                  >
                    {village.name} ({village.code})
                  </option>
                ))}
              </select>

              <label htmlFor="parcel-area">
                Area (hectares)
              </label>

              <input
                id="parcel-area"
                type="number"
                min="0.0001"
                step="0.0001"
                required
                placeholder="Enter area"
                value={form.area_hectares}
                onChange={event =>
                  setForm({
                    ...form,
                    area_hectares: event.target.value
                  })
                }
              />

              <button
                type="submit"
                disabled={saving || !villages.length}
              >
                {saving ? 'Saving...' : 'Register Parcel'}
              </button>

              {formError && (
                <p className="gis-error" role="alert">
                  {formError}
                </p>
              )}
            </form>
          </section>
        )}

        <section className="registry-card">
          <h3>Parcel Records</h3>

          <form
            className="registry-search-form"
            onSubmit={event => {
              event.preventDefault();
              setPage(0);
              setAppliedSearch(search.trim());
            }}
          >
            <input
              className="registry-search"
              placeholder="Search parcel ID, village or record ID"
              aria-label="Search parcels"
              maxLength={100}
              value={search}
              onChange={event =>
                setSearch(event.target.value)
              }
            />

            <button type="submit" disabled={loading}>
              Search
            </button>

            <button
              type="button"
              className="registry-clear"
              disabled={loading && !appliedSearch}
              onClick={() => {
                setSearch('');
                setPage(0);
                setAppliedSearch('');
              }}
            >
              Clear
            </button>
          </form>

          <div className="registry-table-wrap">
            <table className="registry-table">
              <thead>
                <tr>
                  <th>Parcel ID</th>
                  <th>Village</th>
                  <th>Area (ha)</th>
                  <th>Owner</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {parcels.map(parcel => (
                  <tr key={parcel.id}>
                    <td>{parcel.external_id}</td>
                    <td>{parcel.village_code}</td>
                    <td>{parcel.area_hectares}</td>

                    <td>
                      {canEdit ? (
                        <>
                          <select
                            aria-label={`Owner for ${parcel.external_id}`}
                            value={
                              ownerDrafts[parcel.id] ??
                              parcel.farmer_id ??
                              ''
                            }
                            onChange={event =>
                              setOwnerDrafts(values => ({
                                ...values,
                                [parcel.id]: event.target.value
                              }))
                            }
                          >
                            <option value="">
                              Unassigned
                            </option>

                            {farmers.map(farmer => (
                              <option
                                key={farmer.id}
                                value={farmer.id}
                              >
                                {farmer.email}
                              </option>
                            ))}
                          </select>

                          <button
                            type="button"
                            disabled={
                              ownerBusy === parcel.id ||
                              (ownerDrafts[parcel.id] ?? '') ===
                                (parcel.farmer_id ?? '')
                            }
                            onClick={() => assignOwner(parcel)}
                          >
                            {ownerBusy === parcel.id
                              ? 'Saving...'
                              : 'Assign'}
                          </button>
                        </>
                      ) : parcel.farmer_id ? (
                        role === 'farmer'
                          ? 'Assigned to you'
                          : 'Assigned'
                      ) : (
                        'Unassigned'
                      )}
                    </td>

                    <td>
                      <div className="registry-actions">
                        <button
                          type="button"
                          onClick={() => viewParcel(parcel.id)}
                        >
                          View
                        </button>

                        {canEdit && (
                          <button
                            type="button"
                            onClick={() => startEditing(parcel)}
                          >
                            Edit
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}

                {!loading && parcels.length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      No matching parcels found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {loading && <p>Loading parcels...</p>}

          <div className="registry-pagination">
            <span>
              Page {page + 1} Â· {parcels.length}{' '}
              record{parcels.length === 1 ? '' : 's'}
              {hasMore ? ' Â· More results available' : ''}
            </span>

            <div>
              <button
                type="button"
                disabled={page === 0 || loading}
                onClick={() =>
                  setPage(value => Math.max(0, value - 1))
                }
              >
                Previous
              </button>

              <button
                type="button"
                disabled={!hasMore || loading}
                onClick={() =>
                  setPage(value => value + 1)
                }
              >
                Next
              </button>
            </div>
          </div>
        </section>
      </div>

      {editing && canEdit && (
        <section className="registry-card registry-selected">
          <div className="registry-heading">
            <div>
              <h3>Edit Parcel</h3>
              <p>
                Update parcel information without changing
                its owner or geometry.
              </p>
            </div>

            <button
              type="button"
              disabled={editSaving}
              onClick={cancelEditing}
            >
              Cancel
            </button>
          </div>

          <form
            className="registry-form"
            onSubmit={saveParcel}
          >
            <label htmlFor="edit-parcel-id">
              Parcel ID
            </label>

            <input
              id="edit-parcel-id"
              required
              maxLength={100}
              value={editForm.external_id}
              onChange={event =>
                setEditForm({
                  ...editForm,
                  external_id: event.target.value
                })
              }
            />

            <label htmlFor="edit-parcel-village">
              Village
            </label>

            <select
              id="edit-parcel-village"
              required
              value={editForm.village_code}
              onChange={event =>
                setEditForm({
                  ...editForm,
                  village_code: event.target.value
                })
              }
            >
              {!villages.some(
                village => village.code === editForm.village_code
              ) && editForm.village_code && (
                <option value={editForm.village_code}>
                  {editForm.village_code} (current village)
                </option>
              )}

              <option value="">
                Select village
              </option>

              {villages.map(village => (
                <option
                  key={village.code}
                  value={village.code}
                >
                  {village.name} ({village.code})
                </option>
              ))}
            </select>

            <label htmlFor="edit-parcel-area">
              Area (hectares)
            </label>

            <input
              id="edit-parcel-area"
              type="number"
              min="0.0001"
              step="0.0001"
              required
              value={editForm.area_hectares}
              onChange={event =>
                setEditForm({
                  ...editForm,
                  area_hectares: event.target.value
                })
              }
            />

            {editError && (
              <p className="gis-error" role="alert">
                {editError}
              </p>
            )}

            <div className="registry-actions">
              <button
                type="submit"
                disabled={editSaving}
              >
                {editSaving
                  ? 'Saving changes...'
                  : 'Save Changes'}
              </button>

              <button
                type="button"
                disabled={editSaving}
                onClick={cancelEditing}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {selected && (
        <section className="registry-card registry-selected">
          <div className="registry-heading">
            <h3>Parcel Details</h3>

            <button
              type="button"
              onClick={() => setSelected(null)}
            >
              Close
            </button>
          </div>

          <dl>
            <dt>Record ID</dt>
            <dd>{selected.id}</dd>

            <dt>Parcel ID</dt>
            <dd>{selected.external_id}</dd>

            <dt>Village</dt>
            <dd>{selected.village_code}</dd>

            <dt>Area</dt>
            <dd>{selected.area_hectares} hectares</dd>

            <dt>Farmer owner</dt>
            <dd>
              {ownershipLabel(selected.farmer_id, farmers)}
            </dd>

            <dt>Created</dt>
            <dd>{selected.created_at || 'Unavailable'}</dd>
          </dl>
        </section>
      )}

      <ParcelMap />
    </div>
  );
}

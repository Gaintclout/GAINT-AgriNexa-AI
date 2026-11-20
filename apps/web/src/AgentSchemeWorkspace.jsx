import React, { useState } from "react";
import { useAuth } from "./AuthContext";

const statuses = {
  potential_match: "Potential match",
  needs_review: "Needs review",
  not_matched: "Not matched",
};

export default function AgentSchemeWorkspace() {
  const { request } = useAuth();
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [category, setCategory] = useState("");
  const [area, setArea] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setResult(null);

    if (district.trim() && !state.trim()) {
      setError("Enter a state when specifying a district.");
      return;
    }

    const landArea = area.trim() === "" ? null : Number(area);
    if (
      landArea !== null &&
      (!Number.isFinite(landArea) || landArea < 0 || landArea > 100000)
    ) {
      setError("Enter a valid land area.");
      return;
    }

    setLoading(true);
    try {
      const response = await request(
        "/api/v1/agents/schemes/screen",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            state: state.trim() || null,
            district: district.trim() || null,
            farmer_category: category || null,
            land_area_hectares: landArea,
            limit: 20,
          }),
        }
      );
      if (!response.ok) {
        throw new Error(
          response.status === 503
            ? "Verified scheme catalogue is unavailable."
            : response.status === 403
              ? "You do not have permission to access scheme guidance."
              : "Unable to retrieve scheme guidance."
        );
      }
      setResult(await response.json());
    } catch (err) {
      setError(err.message || "Scheme request failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="agent-scheme-workspace">
      <div className="agent-scheme-heading">
        <div>
          <h3>Government scheme guidance</h3>
          <p>
            Discover source-backed schemes and review preliminary
            eligibility against published criteria.
          </p>
        </div>
        <span className="agent-scheme-tag">
          Preliminary screening
        </span>
      </div>

      <form className="agent-scheme-form" onSubmit={submit}>
        <label>
          State
          <input
            value={state}
            maxLength={100}
            onChange={(event) => setState(event.target.value)}
            placeholder="Enter state"
          />
        </label>

        <label>
          District
          <input
            value={district}
            maxLength={100}
            onChange={(event) => setDistrict(event.target.value)}
            placeholder="Enter district"
          />
        </label>

        <label>
          Farmer category
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="">Not specified</option>
            <option value="marginal">Marginal</option>
            <option value="small">Small</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label>
          Land area (hectares)
          <input
            type="number"
            min="0"
            max="100000"
            step="any"
            value={area}
            onChange={(event) => setArea(event.target.value)}
            placeholder="Optional"
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? "Checking schemes..." : "Find schemes"}
        </button>
      </form>

      {error && (
        <p role="alert" className="agent-scheme-error">
          {error}
        </p>
      )}

      {result && (
        <div className="agent-scheme-results">
          <p className="agent-scheme-message">{result.message}</p>
          {result.catalogue_id && (
            <p className="agent-scheme-message">
              Catalogue: {result.catalogue_id} · Dataset: {result.dataset_version || "version unavailable"} · Contract: v{result.catalogue_version} · Published: {result.published_at}
              {result.authority_source_url && (
                <> · Authority: <a href={result.authority_source_url} target="_blank" rel="noopener noreferrer">{result.authority_name}</a></>
              )}
              {result.imported_at && <> · Imported: {result.imported_at} · Approved: {result.approved_at}</>}
            </p>
          )}

          <div className="agent-scheme-grid">
            {result.schemes?.map((scheme) => (
              <article
                key={scheme.scheme_id}
                className="agent-scheme-card"
              >
                <div className="agent-scheme-card-heading">
                  <h4>{scheme.scheme_name}</h4>
                  <span
                    className={`agent-scheme-status status-${scheme.eligibility_status}`}
                  >
                    {statuses[scheme.eligibility_status] || "Review"}
                  </span>
                </div>

                <p>
                  {scheme.government_level === "central"
                    ? "Central government"
                    : "State government"}
                </p>

                <p>
                  Geography: {scheme.states.length ? scheme.states.join(", ") : "All configured states"}
                  {scheme.districts.length ? ` · ${scheme.districts.join(", ")}` : ""}
                </p>

                <strong>Screening explanation</strong>
                <ul>
                  {scheme.eligibility_reasons.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>

                <strong>Documents to review</strong>
                {scheme.documents_required.length ? (
                  <ul>
                    {scheme.documents_required.map((doc, index) => (
                      <li key={index}>{doc}</li>
                    ))}
                  </ul>
                ) : (
                  <p>No document list provided in the catalogue.</p>
                )}

                <strong>Application guidance</strong>
                <p>{scheme.application_guidance}</p>

                <p>
                  Source checked: {scheme.source_verified_on}
                  {" · "}
                  {scheme.source_age_days} days ago
                </p>

                {(scheme.effective_from || scheme.effective_until) && (
                  <p>
                    Effective: {scheme.effective_from || "Not specified"} to {scheme.effective_until || "Open-ended"}
                  </p>
                )}

                <a
                  href={scheme.official_source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  View official source
                </a>
              </article>
            ))}
          </div>

          {result.schemes?.length === 0 && (
            <p className="agent-scheme-message">
              No approved scheme records are available for review.
            </p>
          )}

          <p className="agent-scheme-disclaimer">
            Screening is informational only. Official agencies determine
            eligibility, benefits, application acceptance and approval.
            Always verify current requirements before applying.
          </p>
        </div>
      )}
    </section>
  );
}

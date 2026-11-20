import { useState } from "react";
import { useAuth } from "./AuthContext";

const INDICATORS = [
  ["severe_weather", "Severe weather"],
  ["crop_damage", "Crop damage"],
  ["pest_outbreak", "Pest outbreak"],
  ["irrigation_shortage", "Irrigation shortage"],
  ["market_disruption", "Market disruption"],
  ["scheme_access_issue", "Scheme access issue"],
  ["immediate_personal_danger", "Immediate personal danger"],
];

const SOURCES = [
  ["farmer_report", "Farmer report"],
  ["field_observation", "Field observation"],
  ["verified_weather", "Weather source"],
  ["verified_market", "Market source"],
  ["official_notice", "Official notice"],
  ["other", "Other"],
];

const INITIAL = {
  indicator: "crop_damage",
  description: "",
  source_type: "farmer_report",
  source_reference: "",
  verified: false,
};

export default function AgentEscalationWorkspace() {
  const { request } = useAuth();

  const [caseReference, setCaseReference] = useState("");
  const [district, setDistrict] = useState("");
  const [crop, setCrop] = useState("");
  const [items, setItems] = useState([{ ...INITIAL }]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function update(index, key, value) {
    setItems((previous) =>
      previous.map((item, i) =>
        i === index ? { ...item, [key]: value } : item
      )
    );
    setResult(null);
  }

  function addIndicator() {
    setItems((previous) =>
      previous.length >= 10
        ? previous
        : [...previous, { ...INITIAL }]
    );
    setResult(null);
  }

  function removeIndicator(index) {
    setItems((previous) =>
      previous.length <= 1
        ? previous
        : previous.filter((_, i) => i !== index)
    );
    setResult(null);
  }

  async function submit(event) {
    event.preventDefault();
    if (loading) return;

    setError("");
    setResult(null);

    const reference = caseReference.trim();

    if (reference.length < 3) {
      setError("Enter a case reference of at least 3 characters.");
      return;
    }

    const indicators = items.map((item) => ({
      indicator: item.indicator,
      description: item.description.trim(),
      source_type: item.source_type,
      source_reference:
        item.source_reference.trim() || null,
      verified: item.verified,
    }));

    if (
      indicators.some(
        (item) =>
          item.description.length < 10 ||
          (item.verified && !item.source_reference)
      )
    ) {
      setError(
        "Each indicator needs a description of at least 10 characters. Verified evidence also requires a source reference."
      );
      return;
    }

    setLoading(true);

    try {
      const response = await request(
        "/api/v1/agents/escalation/screen",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            case_reference: reference,
            district: district.trim() || null,
            crop: crop.trim() || null,
            indicators,
          }),
        }
      );

      setResult(response);
    } catch (err) {
      setError(
        err?.message ||
          "Escalation screening could not be completed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="agrinexa-escalation">
      <div className="agrinexa-escalation__header">
        <div>
          <span className="agrinexa-escalation__eyebrow">
            Milestone 10 · Advisory agent
          </span>
          <h2>Risk escalation screening</h2>
          <p>
            Evaluate reported agricultural risks and prepare
            evidence-backed recommendations for human review.
          </p>
        </div>
        <span className="agrinexa-escalation__status">
          Human review required
        </span>
      </div>

      <div className="agrinexa-escalation__notice">
        Screening only. No notification, emergency dispatch,
        government submission, or external action is performed.
      </div>

      <form
        className="agrinexa-escalation__form"
        onSubmit={submit}
      >
        <div className="agrinexa-escalation__grid">
          <label>
            Case reference
            <input
              required
              maxLength={100}
              minLength={3}
              value={caseReference}
              onChange={(event) => {
                setCaseReference(event.target.value);
                setResult(null);
              }}
              placeholder="Example: FIELD-CASE-001"
            />
          </label>

          <label>
            District (optional)
            <input
              maxLength={100}
              value={district}
              onChange={(event) => {
                setDistrict(event.target.value);
                setResult(null);
              }}
              placeholder="District"
            />
          </label>

          <label>
            Crop (optional)
            <input
              maxLength={100}
              value={crop}
              onChange={(event) => {
                setCrop(event.target.value);
                setResult(null);
              }}
              placeholder="Crop name"
            />
          </label>
        </div>

        <div className="agrinexa-escalation__section-title">
          <div>
            <h3>Risk evidence</h3>
            <p>
              Add up to ten observations. Only mark evidence
              verified when its source can be independently checked.
            </p>
          </div>
          <button
            type="button"
            className="agrinexa-escalation__secondary"
            onClick={addIndicator}
            disabled={items.length >= 10}
          >
            Add indicator
          </button>
        </div>

        {items.map((item, index) => (
          <div
            className="agrinexa-escalation__evidence"
            key={index}
          >
            <div className="agrinexa-escalation__evidence-head">
              <strong>Evidence {index + 1}</strong>
              {items.length > 1 && (
                <button
                  type="button"
                  className="agrinexa-escalation__remove"
                  onClick={() => removeIndicator(index)}
                >
                  Remove
                </button>
              )}
            </div>

            <div className="agrinexa-escalation__grid">
              <label>
                Risk indicator
                <select
                  value={item.indicator}
                  onChange={(event) =>
                    update(index, "indicator", event.target.value)
                  }
                >
                  {INDICATORS.map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Evidence source
                <select
                  value={item.source_type}
                  onChange={(event) =>
                    update(index, "source_type", event.target.value)
                  }
                >
                  {SOURCES.map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Source reference
                <input
                  maxLength={500}
                  value={item.source_reference}
                  onChange={(event) =>
                    update(
                      index,
                      "source_reference",
                      event.target.value
                    )
                  }
                  placeholder="Document ID or verified source"
                />
              </label>
            </div>

            <label>
              Observation details
              <textarea
                required
                minLength={10}
                maxLength={1000}
                rows={3}
                value={item.description}
                onChange={(event) =>
                  update(index, "description", event.target.value)
                }
                placeholder="Describe the observed risk and available evidence."
              />
            </label>

            <label className="agrinexa-escalation__checkbox">
              <input
                type="checkbox"
                checked={item.verified}
                onChange={(event) =>
                  update(index, "verified", event.target.checked)
                }
              />
              Source independently verified
            </label>
          </div>
        ))}

        {error && (
          <p className="agrinexa-escalation__error" role="alert">
            {error}
          </p>
        )}

        <button
          className="agrinexa-escalation__primary"
          disabled={loading}
          type="submit"
        >
          {loading
            ? "Evaluating risk..."
            : "Generate escalation assessment"}
        </button>
      </form>

      {result && (
        <div
          className="agrinexa-escalation__result"
          aria-live="polite"
        >
          <div className="agrinexa-escalation__result-header">
            <div>
              <span className="agrinexa-escalation__eyebrow">
                Assessment result
              </span>
              <h3>{result.case_reference}</h3>
              {result.correlation_id && <small>Audit correlation: {result.correlation_id}</small>}
            </div>
            <span
              className={`agrinexa-escalation__severity agrinexa-escalation__severity--${result.severity}`}
            >
              {result.severity} severity
            </span>
          </div>

          <div className="agrinexa-escalation__metrics">
            <div>
              <span>Priority score</span>
              <strong>{result.priority_score}/100</strong>
            </div>
            <div>
              <span>Evidence confidence</span>
              <strong>{result.confidence}</strong>
            </div>
            <div>
              <span>Review priority</span>
              <strong>{result.review_priority}</strong>
            </div>
          </div>

          <div className="agrinexa-escalation__result-section">
            <h4>Evidence and reasons</h4>
            <ul>
              {result.reasons.map((reason, index) => (
                <li key={index}>{reason}</li>
              ))}
            </ul>
          </div>

          <div className="agrinexa-escalation__result-section">
            <h4>Recommended human follow-up</h4>
            <ul>
              {result.recommended_actions.map((action, index) => (
                <li key={index}>{action}</li>
              ))}
            </ul>
          </div>

          <div className="agrinexa-escalation__notice">
            {result.disclaimer}
          </div>
        </div>
      )}
    </section>
  );
}

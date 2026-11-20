import { useState } from "react";
import { useAuth } from "./AuthContext";

const DOMAINS = [
  ["weather", "Weather"],
  ["crop_advisory", "Crop advisory"],
  ["market", "Market intelligence"],
  ["schemes", "Government schemes"],
  ["escalation", "Escalation"],
];

const OUTCOMES = [
  ["helpful", "Helpful"],
  ["inaccurate", "Inaccurate"],
  ["incomplete", "Incomplete"],
  ["outdated", "Outdated"],
  ["unsafe", "Potentially unsafe"],
];

const SOURCES = [
  ["field_observation", "Field observation"],
  ["official_source", "Official source"],
  ["expert_review", "Expert review"],
  ["farmer_report", "Farmer report"],
  ["other", "Other"],
];

const INITIAL = {
  feedback_id: "",
  agent_domain: "crop_advisory",
  recommendation_reference: "",
  outcome: "incomplete",
  explanation: "",
  evidence_description: "",
  source_type: "field_observation",
  source_reference: "",
  verified: false,
};

export default function AgentLearningWorkspace() {
  const { request } = useAuth();

  const [reference, setReference] = useState("");
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

  function addFeedback() {
    setItems((previous) =>
      previous.length >= 25
        ? previous
        : [...previous, { ...INITIAL }]
    );
    setResult(null);
  }

  function removeFeedback(index) {
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

    if (reference.trim().length < 3) {
      setError("Enter a review reference of at least 3 characters.");
      return;
    }

    const feedback = items.map((item) => {
      const evidence = item.evidence_description.trim()
        ? [{
            description: item.evidence_description.trim(),
            source_type: item.source_type,
            source_reference:
              item.source_reference.trim() || null,
            verified: item.verified,
          }]
        : [];

      return {
        feedback_id: item.feedback_id.trim(),
        agent_domain: item.agent_domain,
        recommendation_reference:
          item.recommendation_reference.trim(),
        outcome: item.outcome,
        explanation: item.explanation.trim(),
        evidence,
      };
    });

    const ids = feedback.map((item) => item.feedback_id);

    if (new Set(ids).size !== ids.length) {
      setError("Feedback IDs must be unique.");
      return;
    }

    if (
      feedback.some(
        (item) =>
          item.feedback_id.length < 3 ||
          item.recommendation_reference.length < 3 ||
          item.explanation.length < 10 ||
          item.evidence.some(
            (evidence) =>
              evidence.description.length < 10 ||
              (evidence.verified && !evidence.source_reference)
          )
      )
    ) {
      setError(
        "Check feedback IDs, recommendation references, explanations and evidence details."
      );
      return;
    }

    setLoading(true);

    try {
      const response = await request(
        "/api/v1/agents/learning/review",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            review_reference: reference.trim(),
            feedback,
          }),
        }
      );

      setResult(response);
    } catch (err) {
      setError(
        err?.message ||
          "Learning feedback review could not be completed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="agrinexa-learning">
      <div className="agrinexa-learning__header">
        <div>
          <span className="agrinexa-learning__eyebrow">
            Milestone 11 · Human-supervised AI
          </span>
          <h2>Learning and feedback review</h2>
          <p>
            Evaluate recommendation feedback and prepare
            explainable improvement proposals for human review.
          </p>
        </div>
        <span className="agrinexa-learning__status">
          No automatic model updates
        </span>
      </div>

      <div className="agrinexa-learning__notice">
        Feedback is evaluated in memory only. No feedback is saved,
        no model is retrained, and no production recommendation is changed.
      </div>

      <form
        className="agrinexa-learning__form"
        onSubmit={submit}
      >
        <label>
          Review reference
          <input
            required
            minLength={3}
            maxLength={100}
            value={reference}
            onChange={(event) => {
              setReference(event.target.value);
              setResult(null);
            }}
            placeholder="Example: LEARNING-REVIEW-001"
          />
        </label>

        <div className="agrinexa-learning__section-head">
          <div>
            <h3>Recommendation feedback</h3>
            <p>
              Add up to 25 feedback records. Each record must
              reference an existing recommendation.
            </p>
          </div>
          <button
            type="button"
            className="agrinexa-learning__secondary"
            disabled={items.length >= 25}
            onClick={addFeedback}
          >
            Add feedback
          </button>
        </div>

        {items.map((item, index) => (
          <div
            className="agrinexa-learning__item"
            key={index}
          >
            <div className="agrinexa-learning__item-head">
              <strong>Feedback {index + 1}</strong>
              {items.length > 1 && (
                <button
                  type="button"
                  className="agrinexa-learning__remove"
                  onClick={() => removeFeedback(index)}
                >
                  Remove
                </button>
              )}
            </div>

            <div className="agrinexa-learning__grid">
              <label>
                Feedback ID
                <input
                  required
                  minLength={3}
                  maxLength={100}
                  value={item.feedback_id}
                  onChange={(event) =>
                    update(index, "feedback_id", event.target.value)
                  }
                  placeholder="FB-001"
                />
              </label>

              <label>
                Agent domain
                <select
                  value={item.agent_domain}
                  onChange={(event) =>
                    update(index, "agent_domain", event.target.value)
                  }
                >
                  {DOMAINS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Recommendation reference
                <input
                  required
                  minLength={3}
                  maxLength={150}
                  value={item.recommendation_reference}
                  onChange={(event) =>
                    update(
                      index,
                      "recommendation_reference",
                      event.target.value
                    )
                  }
                  placeholder="REC-001"
                />
              </label>

              <label>
                Feedback outcome
                <select
                  value={item.outcome}
                  onChange={(event) =>
                    update(index, "outcome", event.target.value)
                  }
                >
                  {OUTCOMES.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              Feedback explanation
              <textarea
                required
                minLength={10}
                maxLength={1500}
                rows={3}
                value={item.explanation}
                onChange={(event) =>
                  update(index, "explanation", event.target.value)
                }
                placeholder="Explain what was helpful, incorrect, incomplete, outdated or unsafe."
              />
            </label>

            <div className="agrinexa-learning__evidence">
              <h4>Supporting evidence (optional)</h4>

              <label>
                Evidence description
                <textarea
                  minLength={10}
                  maxLength={1000}
                  rows={2}
                  value={item.evidence_description}
                  onChange={(event) =>
                    update(
                      index,
                      "evidence_description",
                      event.target.value
                    )
                  }
                  placeholder="Describe any supporting observation or source."
                />
              </label>

              <div className="agrinexa-learning__grid">
                <label>
                  Source type
                  <select
                    value={item.source_type}
                    onChange={(event) =>
                      update(index, "source_type", event.target.value)
                    }
                  >
                    {SOURCES.map(([value, label]) => (
                      <option key={value} value={value}>
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
                    placeholder="Document ID or source reference"
                  />
                </label>
              </div>

              <label className="agrinexa-learning__checkbox">
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
          </div>
        ))}

        {error && (
          <p
            className="agrinexa-learning__error"
            role="alert"
          >
            {error}
          </p>
        )}

        <button
          className="agrinexa-learning__primary"
          type="submit"
          disabled={loading}
        >
          {loading
            ? "Evaluating feedback..."
            : "Generate learning review"}
        </button>
      </form>

      {result && (
        <div
          className="agrinexa-learning__result"
          aria-live="polite"
        >
          <div className="agrinexa-learning__result-head">
            <div>
              <span className="agrinexa-learning__eyebrow">
                Learning review
              </span>
              <h3>{result.review_reference}</h3>
              {result.correlation_id && <small>Audit correlation: {result.correlation_id}</small>}
            </div>
            <span className="agrinexa-learning__priority">
              {result.review_priority} review
            </span>
          </div>

          <div className="agrinexa-learning__metrics">
            <div>
              <span>Feedback assessed</span>
              <strong>{result.feedback_count}</strong>
            </div>
            <div>
              <span>Human approval</span>
              <strong>Required</strong>
            </div>
            <div>
              <span>Model updated</span>
              <strong>No</strong>
            </div>
          </div>

          <h4>Feedback findings</h4>
          <div className="agrinexa-learning__findings">
            {result.findings.map((finding) => (
              <div
                className="agrinexa-learning__finding"
                key={finding.feedback_id}
              >
                <strong>{finding.feedback_id}</strong>
                <span>{finding.agent_domain}</span>
                <span>{finding.assessment.replaceAll("_", " ")}</span>
                <p>{finding.recommendation}</p>
                <small>
                  Evidence: {finding.evidence_status.replaceAll("_", " ")}
                </small>
              </div>
            ))}
          </div>

          <h4>Improvement proposals</h4>
          <ul>
            {result.improvement_proposals.map(
              (proposal, index) => (
                <li key={index}>{proposal}</li>
              )
            )}
          </ul>

          <div className="agrinexa-learning__notice">
            {result.disclaimer}
          </div>
        </div>
      )}
    </section>
  );
}

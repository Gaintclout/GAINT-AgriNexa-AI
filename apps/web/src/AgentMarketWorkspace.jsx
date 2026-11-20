import React, { useState } from "react";
import { useAuth } from "./AuthContext";

const commodities = [
  "rice",
  "wheat",
  "maize",
  "cotton",
  "groundnut",
  "tomato",
];

const formatLabel = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());

const formatPrice = (value) =>
  typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2,
      }).format(value)
    : "Unavailable";

export default function AgentMarketWorkspace() {
  const { request } = useAuth();

  const [commodity, setCommodity] = useState("rice");
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");
  const [market, setMarket] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const searchPrices = async (event) => {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);

    try {
      const response = await request(
        "/api/v1/agents/market/prices",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            commodity,
            state: state.trim() || null,
            district: district.trim() || null,
            market: market.trim() || null,
            limit: 20,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          response.status === 503
            ? "Verified market data is temporarily unavailable."
            : response.status === 403
              ? "You do not have permission to access market intelligence."
              : "Unable to retrieve market intelligence."
        );
      }

      setResult(await response.json());
    } catch (err) {
      setError(
        err.message || "Market intelligence request failed."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="agent-market-workspace">
      <div className="agent-market-heading">
        <div>
          <h3>Market intelligence</h3>
          <p>
            Compare verified agricultural commodity prices
            with transparent sources and dates.
          </p>
        </div>
        <span className="agent-market-tag">
          Source-verified records only
        </span>
      </div>

      <form
        className="agent-market-form"
        onSubmit={searchPrices}
      >
        <label>
          Commodity
          <select
            value={commodity}
            onChange={(event) =>
              setCommodity(event.target.value)
            }
          >
            {commodities.map((item) => (
              <option key={item} value={item}>
                {formatLabel(item)}
              </option>
            ))}
          </select>
        </label>

        <label>
          State (optional)
          <input
            type="text"
            maxLength={100}
            value={state}
            onChange={(event) =>
              setState(event.target.value)
            }
            placeholder="Enter state"
          />
        </label>

        <label>
          District (optional)
          <input
            type="text"
            maxLength={100}
            value={district}
            onChange={(event) =>
              setDistrict(event.target.value)
            }
            placeholder="Enter district"
          />
        </label>

        <label>
          Market (optional)
          <input
            type="text"
            maxLength={120}
            value={market}
            onChange={(event) => setMarket(event.target.value)}
            placeholder="Enter mandi or market"
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading
            ? "Checking market prices..."
            : "Check market prices"}
        </button>
      </form>

      {error && (
        <p className="agent-market-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className="agent-market-results">
          <div className="agent-market-summary">
            <h4>
              {formatLabel(result.commodity)} market prices
            </h4>
            <p>{result.message}</p>
            <small>
              Source status:{" "}
              {formatLabel(result.source_status)}
            </small>
            {result.snapshot_id && (
              <div>
                <small>
                  Snapshot: {result.snapshot_id} · Dataset: {result.dataset_version || "version unavailable"} · Contract: v{result.snapshot_version} · Published: {result.published_at}
                </small>
                {result.imported_at && <small>Imported: {result.imported_at} · Approved: {result.approved_at}</small>}
                <small>
                  Source: {result.snapshot_source_url ? (
                    <a href={result.snapshot_source_url} target="_blank" rel="noopener noreferrer">
                      {result.snapshot_source_name}
                    </a>
                  ) : result.snapshot_source_name}
                </small>
              </div>
            )}
          </div>

          {result.records?.length > 0 && (
            <div className="agent-market-table-wrap">
              <table className="agent-market-table">
                <thead>
                  <tr>
                    <th>Market</th>
                    <th>District</th>
                    <th>State</th>
                    <th>Price date</th>
                    <th>Minimum</th>
                    <th>Modal</th>
                    <th>Maximum</th>
                    <th>Freshness</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {result.records.map((item, index) => (
                    <tr
                      key={`${item.market}-${item.price_date}-${index}`}
                    >
                      <td>
                        {item.market}
                        {(item.variety || item.grade) && (
                          <small>
                            {item.variety || "Variety unavailable"}
                            {item.grade ? ` · ${item.grade}` : ""}
                          </small>
                        )}
                      </td>
                      <td>{item.district}</td>
                      <td>{item.state}</td>
                      <td>{item.price_date}</td>
                      <td>
                        {formatPrice(
                          item.min_price_inr_per_quintal
                        )}
                      </td>
                      <td>
                        <strong>
                          {formatPrice(
                            item.modal_price_inr_per_quintal
                          )}
                        </strong>
                      </td>
                      <td>
                        {formatPrice(
                          item.max_price_inr_per_quintal
                        )}
                      </td>
                      <td>
                        <span
                          className={`agent-market-freshness freshness-${item.freshness}`}
                        >
                          {formatLabel(item.freshness)}
                          {" · "}
                          {item.age_days} days
                        </span>
                      </td>
                      <td>
                        {item.source_url ? (
                          <a
                            href={item.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {item.source_name}
                          </a>
                        ) : (
                          item.source_name
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {result.records?.length === 0 && (
            <p className="agent-market-disclaimer">
              No approved market records are available for the selected commodity and geography.
            </p>
          )}

          <p className="agent-market-disclaimer">
            Geography: {result.state || "all available states"}{result.district ? ` · ${result.district}` : ""}.
            {" "}
            Prices are in the preserved source unit (currently INR per quintal). Records may be
            delayed or incomplete. These are market
            observations, not guaranteed selling prices.
            Verify the source and date before making decisions.
          </p>
        </div>
      )}
    </section>
  );
}

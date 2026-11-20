import React, { useState } from "react";
import { useAuth } from "./AuthContext";

const formatValue = (value, suffix = "") =>
  typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(1)}${suffix}`
    : "Unavailable";

export default function AgentWeatherWorkspace() {
  const { request } = useAuth();
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [cropName, setCropName] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const loadForecast = async (event) => {
    event.preventDefault();
    setError("");
    setResult(null);

    if (
      latitude.trim() === "" ||
      longitude.trim() === ""
    ) {
      setError("Enter both latitude and longitude.");
      return;
    }

    const lat = Number(latitude);
    const lon = Number(longitude);

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      lat < -90 ||
      lat > 90 ||
      lon < -180 ||
      lon > 180
    ) {
      setError("Enter valid geographic coordinates.");
      return;
    }

    setLoading(true);

    try {
      const response = await request(
        "/api/v1/agents/weather/forecast",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            latitude: lat,
            longitude: lon,
            crop_name: cropName.trim() || null,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          response.status === 503
            ? "Weather provider is temporarily unavailable."
            : response.status === 403
              ? "You do not have permission to access weather intelligence."
              : "Unable to retrieve weather forecast."
        );
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Weather request failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="agent-weather-workspace">
      <div className="agent-weather-heading">
        <div>
          <h3>Weather intelligence</h3>
          <p>
            Location-based agricultural forecast and weather risk guidance.
          </p>
        </div>
        <span className="agent-weather-tag">Read-only advisory</span>
      </div>

      <form className="agent-weather-form" onSubmit={loadForecast}>
        <label>
          Latitude
          <input
            type="number"
            step="any"
            min="-90"
            max="90"
            value={latitude}
            onChange={(event) => setLatitude(event.target.value)}
            placeholder="Example: 17.385"
            required
          />
        </label>

        <label>
          Longitude
          <input
            type="number"
            step="any"
            min="-180"
            max="180"
            value={longitude}
            onChange={(event) => setLongitude(event.target.value)}
            placeholder="Example: 78.4867"
            required
          />
        </label>

        <label>
          Crop name (optional)
          <input
            type="text"
            maxLength={80}
            value={cropName}
            onChange={(event) => setCropName(event.target.value)}
            placeholder="Enter crop"
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? "Fetching forecast..." : "Get weather forecast"}
        </button>
      </form>

      {error && (
        <p className="agent-weather-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className="agent-weather-results">
          <div className="agent-weather-result-header">
            <h4>Forecast for {result.forecast_date}</h4>
            <span>{result.source}</span>
          </div>

          <div className="agent-weather-metrics">
            <article>
              <span>Maximum temperature</span>
              <strong>
                {formatValue(result.temperature_max_c, " °C")}
              </strong>
            </article>

            <article>
              <span>Minimum temperature</span>
              <strong>
                {formatValue(result.temperature_min_c, " °C")}
              </strong>
            </article>

            <article>
              <span>Rainfall</span>
              <strong>
                {formatValue(result.rainfall_mm, " mm")}
              </strong>
            </article>

            <article>
              <span>Maximum wind speed</span>
              <strong>
                {formatValue(result.wind_max_kmh, " km/h")}
              </strong>
            </article>

            <article>
              <span>Rain probability</span>
              <strong>
                {formatValue(
                  result.precipitation_probability_max,
                  "%"
                )}
              </strong>
            </article>
          </div>

          <div className="agent-weather-risks">
            <h4>Agricultural weather alerts</h4>

            {result.risks?.length ? (
              result.risks.map((risk) => (
                <article
                  className={`agent-weather-risk severity-${risk.severity}`}
                  key={risk.code}
                >
                  <strong>{risk.title}</strong>
                  <p>{risk.recommendation}</p>
                </article>
              ))
            ) : (
              <p>
                No threshold-based weather alerts detected in this forecast.
              </p>
            )}
          </div>

          <p className="agent-weather-disclaimer">
            Forecast information is advisory only. Verify local field
            conditions before making agricultural decisions.
          </p>
        </div>
      )}
    </section>
  );
}

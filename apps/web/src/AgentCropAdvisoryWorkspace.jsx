import React, { useState } from "react";
import { useAuth } from "./AuthContext";

const crops = [
  "rice",
  "wheat",
  "maize",
  "cotton",
  "groundnut",
  "tomato",
];

const stages = [
  "establishment",
  "vegetative",
  "flowering",
  "harvest",
];

const label = (value) =>
  value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function AgentCropAdvisoryWorkspace() {
  const { request } = useAuth();

  const [crop, setCrop] = useState("rice");
  const [stage, setStage] = useState("vegetative");
  const [includeWeather, setIncludeWeather] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const generate = async (event) => {
    event.preventDefault();
    setError("");
    setResult(null);

    let lat = null;
    let lon = null;

    if (includeWeather) {
      if (!latitude.trim() || !longitude.trim()) {
        setError("Enter both coordinates for weather integration.");
        return;
      }

      lat = Number(latitude);
      lon = Number(longitude);

      if (
        !Number.isFinite(lat) ||
        !Number.isFinite(lon) ||
        lat < -90 ||
        lat > 90 ||
        lon < -180 ||
        lon > 180
      ) {
        setError("Enter valid latitude and longitude.");
        return;
      }
    }

    setLoading(true);

    try {
      const response = await request(
        "/api/v1/agents/crop-advisory/generate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            crop_name: crop,
            growth_stage: stage,
            latitude: lat,
            longitude: lon,
            include_weather: includeWeather,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          response.status === 403
            ? "You do not have permission to access crop advisory."
            : response.status === 422
              ? "Check the crop advisory inputs."
              : "Crop advisory is temporarily unavailable."
        );
      }

      setResult(await response.json());
    } catch (err) {
      setError(err.message || "Unable to generate advisory.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="agent-crop-workspace">
      <div className="agent-crop-heading">
        <div>
          <h3>Crop advisory intelligence</h3>
          <p>
            Explainable crop-stage guidance with optional weather risks.
          </p>
        </div>
        <span className="agent-crop-tag">Read-only advisory</span>
      </div>

      <form className="agent-crop-form" onSubmit={generate}>
        <label>
          Crop
          <select
            value={crop}
            onChange={(event) => setCrop(event.target.value)}
          >
            {crops.map((item) => (
              <option key={item} value={item}>
                {label(item)}
              </option>
            ))}
          </select>
        </label>

        <label>
          Growth stage
          <select
            value={stage}
            onChange={(event) => setStage(event.target.value)}
          >
            {stages.map((item) => (
              <option key={item} value={item}>
                {label(item)}
              </option>
            ))}
          </select>
        </label>

        <label className="agent-crop-check">
          <input
            type="checkbox"
            checked={includeWeather}
            onChange={(event) =>
              setIncludeWeather(event.target.checked)
            }
          />
          Include weather forecast
        </label>

        {includeWeather && (
          <>
            <label>
              Latitude
              <input
                type="number"
                step="any"
                min="-90"
                max="90"
                required
                value={latitude}
                onChange={(event) =>
                  setLatitude(event.target.value)
                }
              />
            </label>

            <label>
              Longitude
              <input
                type="number"
                step="any"
                min="-180"
                max="180"
                required
                value={longitude}
                onChange={(event) =>
                  setLongitude(event.target.value)
                }
              />
            </label>
          </>
        )}

        <button type="submit" disabled={loading}>
          {loading ? "Generating advisory..." : "Generate crop advisory"}
        </button>
      </form>

      {error && (
        <p className="agent-crop-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className="agent-crop-results">
          <div className="agent-crop-summary">
            <h4>
              {label(result.crop_name)} — {label(result.growth_stage)}
            </h4>
            <p>
              Weather: {label(result.weather_status)}
              {result.weather_forecast_date
                ? ` · ${result.weather_forecast_date}`
                : ""}
            </p>
          </div>

          {result.weather_status === "unavailable" && (
            <p className="agent-crop-notice">
              Weather data was unavailable. The guidance below does
              not include current forecast risks.
            </p>
          )}

          <div className="agent-crop-advisories">
            {result.advisories.map((item) => (
              <article
                key={item.code}
                className={`agent-crop-item severity-${item.severity}`}
              >
                <div className="agent-crop-item-heading">
                  <strong>{item.title}</strong>
                  <span>{label(item.severity)}</span>
                </div>
                <p>{item.explanation}</p>
                <p>{item.recommendation}</p>
                <small>
                  Evidence: {label(item.evidence_source)}
                </small>
              </article>
            ))}
          </div>

          <p className="agent-crop-disclaimer">
            General advisory only. No disease diagnosis, chemical
            prescription or guaranteed yield prediction is provided.
            Verify recommendations with qualified agricultural
            professionals and local field conditions.
          </p>
        </div>
      )}
    </section>
  );
}


import React, {
  useCallback,
  useEffect,
  useState
} from 'react';

import {
  MapContainer,
  TileLayer,
  GeoJSON,
  useMapEvents
} from 'react-leaflet';

import {
  MapPinned,
  Map,
  Search
} from 'lucide-react';

import 'leaflet/dist/leaflet.css';

import { loadParcels } from './gisApi.js';
import { useAuth } from './AuthContext.jsx';

const EMPTY = {
  type: 'FeatureCollection',
  features: []
};

function Viewport({ onBounds }) {
  const map = useMapEvents({
    moveend: () => onBounds(map.getBounds()),
    zoomend: () => onBounds(map.getBounds())
  });

  useEffect(() => {
    onBounds(map.getBounds());
  }, [map, onBounds]);

  return null;
}

export default function ParcelMap() {
  const { session, logout } = useAuth();

  const token = session?.token || '';
  const isFarmer = session?.principal?.role === 'farmer';

  const [villageFilter, setVillageFilter] = useState('');
  const [parcelFilter, setParcelFilter] = useState('');
  const [appliedFilters, setAppliedFilters] = useState({});

  const [bounds, setBounds] = useState(null);
  const [data, setData] = useState(EMPTY);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onBounds = useCallback(b => {
    setBounds({
      west: b.getWest(),
      south: b.getSouth(),
      east: b.getEast(),
      north: b.getNorth()
    });
  }, []);

  // Existing map API and authorization behavior
  useEffect(() => {
    if (!token) {
      setData(EMPTY);
      setSelected(null);
      return;
    }

    if (!bounds) return;

    const controller = new AbortController();
    let active = true;

    async function run() {
      setLoading(true);
      setError('');

      try {
        const features = await loadParcels(
          token,
          bounds,
          controller.signal,
          appliedFilters
        );

        if (active) {
          setData(features);
          setSelected(null);
        }

      } catch (e) {
        if (active && e.name !== 'AbortError') {
          if (e.authFailure) {
            logout(e.message);
          } else {
            setError(e.message);
            setData(EMPTY);
          }
        }

      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    run();

    return () => {
      active = false;
      controller.abort();
    };

  }, [token, bounds, logout, appliedFilters]);

  return (
    <section
      className={
        isFarmer
          ? 'gis-panel farmer-map-panel'
          : 'gis-panel'
      }
    >

      <div className="gis-head">
        <div>

          <h2>
            {isFarmer ? 'My Land Map' : 'Parcel GIS map'}
          </h2>

          <p>
            {isFarmer
              ? 'View your land boundaries on the map.'
              : 'Secured PostGIS boundaries · viewport search'}
          </p>

        </div>
      </div>

      {error && (
        <p className="gis-error" role="alert">
          {error}
        </p>
      )}

      <form
        className="gis-login"
        onSubmit={e => {
          e.preventDefault();

          setAppliedFilters({
            village_code: villageFilter.trim(),
            external_id: parcelFilter.trim()
          });
        }}
      >

        <label>
          {isFarmer ? 'Find land on map' : 'Filter map parcels'}
        </label>

        <input
          aria-label="Village code"
          maxLength={100}
          placeholder="Village code"
          value={villageFilter}
          onChange={e => setVillageFilter(e.target.value)}
        />

        <input
          aria-label={isFarmer ? 'Land ID' : 'Parcel ID'}
          maxLength={100}
          placeholder={isFarmer ? 'Land ID' : 'Parcel ID'}
          value={parcelFilter}
          onChange={e => setParcelFilter(e.target.value)}
        />

        <button type="submit" disabled={!token}>
          {isFarmer && <Search size={18} aria-hidden="true" />}
          {isFarmer ? 'Search map' : 'Apply filters'}
        </button>

        <button
          type="button"
          disabled={!token}
          onClick={() => {
            setVillageFilter('');
            setParcelFilter('');
            setAppliedFilters({});
          }}
        >
          Clear
        </button>

      </form>

      {isFarmer && (
        <div className="farmer-map-instructions">
          <Map size={20} aria-hidden="true" />
          <p>
            Move or zoom the map to your village.
            Tap a land boundary to view its details.
          </p>
        </div>
      )}

      <div className="gis-layout">

        <div className="gis-map">

          <MapContainer
            center={[17.385, 78.4867]}
            zoom={10}
            scrollWheelZoom
            style={{
              height: '100%',
              width: '100%'
            }}
          >

            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            <Viewport onBounds={onBounds} />

            {token && data.features.map(f => (
              <GeoJSON
                key={f.id + JSON.stringify(f.geometry)}
                data={f}
                style={{
                  color: selected?.id === f.id
                    ? '#f59e0b'
                    : '#1c8a58',
                  weight: isFarmer ? 3 : 2,
                  fillOpacity: .2
                }}
                eventHandlers={{
                  click: () => setSelected(f)
                }}
              />
            ))}

          </MapContainer>

        </div>

        <aside className="gis-details">

          <h3>
            {isFarmer && (
              <MapPinned size={22} aria-hidden="true" />
            )}

            {isFarmer ? 'Land details' : 'Parcel details'}
          </h3>

          <p aria-live="polite">
            {loading
              ? isFarmer
                ? 'Loading land boundaries...'
                : 'Loading map parcels...'
              : token
                ? `${data.features.length} ${
                    isFarmer
                      ? 'land records visible on map'
                      : 'parcels in viewport'
                  }`
                : 'Sign in to load land boundaries'}
          </p>

          {selected ? (
            <dl>

              <dt>{isFarmer ? 'Land ID' : 'Parcel'}</dt>
              <dd>{selected.properties?.external_id}</dd>

              <dt>Village code</dt>
              <dd>{selected.properties?.village_code}</dd>

              <dt>Record ID</dt>
              <dd>{selected.id}</dd>

            </dl>
          ) : (
            <p>
              {isFarmer
                ? 'Tap a land boundary to see its information.'
                : 'Select a boundary to inspect its details.'}
            </p>
          )}

          {isFarmer &&
           token &&
           !loading &&
           !error &&
           data.features.length === 0 && (
            <p className="farmer-map-empty">
              No land boundaries are visible in this map area.
              Try moving the map or clearing the filters.
            </p>
          )}

        </aside>

      </div>

    </section>
  );
}

import React from 'react';

import {
  Sprout,
  Leaf,
  Droplets,
  CloudRain,
  Info
} from 'lucide-react';

import SpectralIndices from './SpectralIndices.jsx';
import { useAuth } from './AuthContext.jsx';

const INDICES = [
  {
    name: 'NDVI',
    title: 'Vegetation index',
    description: 'Normalized Difference Vegetation Index',
    icon: Leaf,
    theme: 'green'
  },
  {
    name: 'NDWI',
    title: 'Water index',
    description: 'Normalized Difference Water Index',
    icon: Droplets,
    theme: 'blue'
  },
  {
    name: 'NDMI',
    title: 'Moisture index',
    description: 'Normalized Difference Moisture Index',
    icon: CloudRain,
    theme: 'orange'
  }
];

export default function CropIntelligence() {

  const { request } = useAuth();

  return (
    <section className="crop-workspace crop-modern-workspace">

      <div className="crop-modern-heading">

        <div>
          <span className="crop-modern-label">
            <Sprout size={18} aria-hidden="true" />
            Agricultural intelligence
          </span>

          <h1>Crop Intelligence</h1>

          <p>
            Calculate vegetation, water and moisture
            indices using spectral measurements and
            backend-validated inputs.
          </p>
        </div>

        <div className="crop-modern-art" aria-hidden="true">
          <Sprout size={90} strokeWidth={1.3} />
        </div>

      </div>

      <div className="crop-index-overview">

        {INDICES.map(item => {

          const Icon = item.icon;

          return (
            <article
              key={item.name}
              className={`crop-index-info crop-index-${item.theme}`}
            >
              <Icon size={27} aria-hidden="true" />

              <h2>{item.name}</h2>

              <strong>{item.title}</strong>

              <p>{item.description}</p>
            </article>
          );
        })}

      </div>

      <SpectralIndices request={request} />

      <div className="crop-interpretation-note">

        <Info size={24} aria-hidden="true" />

        <div>
          <h3>Expert interpretation</h3>

          <p>
            Spectral indices provide measurements for
            agricultural analysis. They do not independently
            establish crop health, disease or irrigation needs.
          </p>
        </div>

      </div>

    </section>
  );
}

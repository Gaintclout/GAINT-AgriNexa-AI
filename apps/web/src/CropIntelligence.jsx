import React from 'react';
import SpectralIndices from './SpectralIndices.jsx';
import { useAuth } from './AuthContext.jsx';

export default function CropIntelligence() {
  const { request } = useAuth();

  return (
    <section className="crop-workspace">
      <div className="crop-heading">
        <div>
          <span className="eyebrow">CROP INTELLIGENCE</span>
          <h1>Crop spectral indices</h1>
          <p>Calculate NDVI, NDWI, and NDMI using the API's sensor-aware validation. Outputs are inputs for expert interpretation, not a crop diagnosis.</p>
        </div>
      </div>
      <SpectralIndices request={request} />
    </section>
  );
}

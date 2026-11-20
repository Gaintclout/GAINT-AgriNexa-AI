"""Review required STAC band metadata without fetching assets."""
from .scim_contracts import SatelliteProvider

REQUIRED = {
    SatelliteProvider.sentinel_2: ('red', 'green', 'nir', 'swir16'),
    SatelliteProvider.landsat_8: ('red', 'green', 'nir08', 'swir16'),
    SatelliteProvider.landsat_9: ('red', 'green', 'nir08', 'swir16'),
}

def review_assets(provider: SatelliteProvider, assets: dict) -> dict:
    if not isinstance(assets, dict):
        raise ValueError('Assets must be an object')
    available = [key for key in REQUIRED[provider] if isinstance(assets.get(key), dict) and isinstance(assets[key].get('href'), str) and bool(assets[key]['href'].strip())]
    missing = [key for key in REQUIRED[provider] if key not in available]
    return {'available_bands': available, 'missing_bands': missing, 'complete': not missing}

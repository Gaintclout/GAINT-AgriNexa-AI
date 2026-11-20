"""Read-only STAC asset inspection. Never downloads or approves imagery."""
from .scim_asset_review import REQUIRED
from .scim_asset_url_policy import validate_asset_url
from .scim_contracts import SatelliteProvider

QUALITY_ASSET = {
    SatelliteProvider.sentinel_2: "scl",
    SatelliteProvider.landsat_8: "qa_pixel",
    SatelliteProvider.landsat_9: "qa_pixel",
}

def inspect_scene_assets(provider: SatelliteProvider, feature: dict) -> dict:
    """Report eligibility per band without leaking signed URLs into reports.

    A valid URL is not an integrity guarantee or permission to download.
    """
    if not isinstance(feature, dict) or not isinstance(feature.get("assets"), dict):
        raise ValueError("STAC feature must contain an assets object")
    assets = feature["assets"]
    required = (*REQUIRED[provider], QUALITY_ASSET[provider])
    inspection = {}
    for key in required:
        asset = assets.get(key)
        if not isinstance(asset, dict) or not isinstance(asset.get("href"), str):
            inspection[key] = {"status": "missing"}
            continue
        try:
            validate_asset_url(asset["href"])
        except ValueError:
            inspection[key] = {"status": "untrusted_url"}
        else:
            inspection[key] = {"status": "url_policy_passed"}
    return {
        "scene_id": str(feature.get("id", ""))[:200],
        "provider": provider.value,
        "assets": inspection,
        "all_urls_policy_passed": all(v["status"] == "url_policy_passed" for v in inspection.values()),
        "provenance_verified": False,
        "checksum_verified": False,
        "download_authorized": False,
        "real_scene_validation_complete": False,
    }

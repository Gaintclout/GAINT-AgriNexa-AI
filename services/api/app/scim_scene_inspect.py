"""Offline STAC scene inspection CLI; no network, raster downloads, or database writes.

Usage:
python -m app.scim_scene_inspect --stac scene.json --provider sentinel-2 --scene-id ID
"""
import argparse
import json
from pathlib import Path
from .scim_asset_inspection import inspect_scene_assets
from .scim_catalog import COLLECTIONS
from .scim_contracts import SatelliteProvider

MAX_STAC_BYTES = 1_000_000

def inspect_stac_scene(payload: dict, provider: SatelliteProvider, scene_id: str) -> dict:
    if not isinstance(payload, dict) or not isinstance(scene_id, str) or not scene_id:
        raise ValueError("Invalid STAC payload or scene ID")
    if payload.get("type") == "Feature":
        features = [payload]
    elif payload.get("type") == "FeatureCollection" and isinstance(payload.get("features"), list):
        features = payload["features"]
    else:
        raise ValueError("Expected STAC Feature or FeatureCollection")
    matches = [f for f in features if isinstance(f, dict) and f.get("id") == scene_id]
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching scene")
    feature = matches[0]
    if feature.get("type") != "Feature" or feature.get("collection") != COLLECTIONS[provider]:
        raise ValueError("Scene collection does not match provider")
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Missing STAC scene properties")
    platform = properties.get("platform")
    if provider in (SatelliteProvider.landsat_8, SatelliteProvider.landsat_9) and platform != provider.value:
        raise ValueError("Landsat platform does not match provider")
    if provider == SatelliteProvider.sentinel_2 and platform not in ("sentinel-2a", "sentinel-2b", "sentinel-2c"):
        raise ValueError("Sentinel platform does not match provider")
    report = inspect_scene_assets(provider, feature)
    report["collection"] = feature["collection"]
    report["platform"] = platform
    report["metadata_only"] = True
    return report

def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect locally saved STAC scene asset metadata")
    parser.add_argument("--stac", type=Path, required=True)
    parser.add_argument("--provider", type=SatelliteProvider, choices=list(SatelliteProvider), required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.stac.stat().st_size > MAX_STAC_BYTES:
            raise ValueError("STAC file exceeds size limit")
        payload = json.loads(args.stac.read_text(encoding="utf-8"))
        report = inspect_stac_scene(payload, args.provider, args.scene_id)
        result = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(result, encoding="utf-8")
        else:
            print(result, end="")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, f"SCIM scene inspection failed: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())

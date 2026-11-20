"""Retrieve an exact STAC scene from the fixed Earth Search endpoint, metadata only."""
import argparse
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener
from .scim_catalog import COLLECTIONS
from .scim_contracts import SatelliteProvider
from .scim_discovery import EARTH_SEARCH_URL, MAX_RESPONSE_BYTES, NoRedirects, CatalogUnavailable
from .scim_scene_inspect import inspect_stac_scene

SCENE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")

def parse_exact_scene(payload: dict, provider: SatelliteProvider, scene_id: str) -> dict:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise CatalogUnavailable("Invalid STAC response")
    features = payload.get("features")
    if not isinstance(features, list) or len(features) > 1:
        raise CatalogUnavailable("Unexpected STAC feature count")
    try:
        return inspect_stac_scene(payload, provider, scene_id)
    except (ValueError, TypeError) as exc:
        raise CatalogUnavailable("Scene not found or metadata invalid") from exc

def retrieve_scene_report(provider: SatelliteProvider, scene_id: str, *, opener=None) -> dict:
    if not isinstance(scene_id, str) or not SCENE_ID_PATTERN.fullmatch(scene_id):
        raise ValueError("Invalid scene ID")
    body = json.dumps({"collections": [COLLECTIONS[provider]], "ids": [scene_id], "limit": 1}).encode("utf-8")
    request = Request(EARTH_SEARCH_URL, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/geo+json",
        "User-Agent": "GAINT-AgriNexa-SCIM/0.1",
    }, method="POST")
    client = opener if opener is not None else build_opener(NoRedirects())
    try:
        with client.open(request, timeout=10) as response:
            if response.status != 200:
                raise CatalogUnavailable("Satellite catalog returned an error")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CatalogUnavailable("Satellite catalog is temporarily unavailable") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise CatalogUnavailable("Satellite catalog response exceeds size limit")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise CatalogUnavailable("Invalid STAC JSON") from exc
    return parse_exact_scene(payload, provider, scene_id)

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only exact scene metadata retrieval and asset inspection")
    parser.add_argument("--provider", type=SatelliteProvider, choices=list(SatelliteProvider), required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = retrieve_scene_report(args.provider, args.scene_id)
        result = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(result, encoding="utf-8")
        else:
            print(result, end="")
        return 0
    except (OSError, ValueError, CatalogUnavailable) as exc:
        parser.exit(2, f"SCIM scene retrieval failed: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())

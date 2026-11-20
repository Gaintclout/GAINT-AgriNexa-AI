"""Read-only satellite scene discovery for a local WGS84 parcel GeoJSON.

No raster download, database writes, or scene provenance approval.
Run: python -m app.scim_parcel_discovery --parcel tests/fixtures/scim_siddipet_sample_parcel.geojson --start 2026-01-01 --end 2026-02-01
"""
import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path
from .scim_catalog import CatalogSearch
from .scim_discovery import CatalogUnavailable, discover_scenes
from .scim_parcel_catalog import parcel_bbox

PROVIDERS = ("sentinel-2", "landsat-8", "landsat-9")

def discover_parcel(geometry: dict, start: datetime, end: datetime,
                    *, max_cloud_percent: float = 30, limit: int = 20,
                    discover=discover_scenes) -> dict:
    west, south, east, north = parcel_bbox(geometry)
    results = {}
    for provider in PROVIDERS:
        search = CatalogSearch(
            provider=provider, west=west, south=south, east=east, north=north,
            start=start, end=end, max_cloud_percent=max_cloud_percent, limit=limit)
        catalog = discover(search)
        results[provider] = catalog.model_dump(mode="json")
    return {"status": "catalog_metadata_only", "parcel_bbox": [west, south, east, north],
            "search_start": start.isoformat(), "search_end": end.isoformat(),
            "providers": results, "real_scene_validation_complete": False}

def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Earth Search scene discovery for a local SCIM parcel")
    parser.add_argument("--parcel", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--max-cloud-percent", type=float, default=30)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.parcel.stat().st_size > 100_000:
            raise ValueError("Parcel file exceeds size limit")
        geometry = json.loads(args.parcel.read_text(encoding="utf-8"))
        start = datetime.combine(args.start, time.min, tzinfo=timezone.utc)
        end = datetime.combine(args.end, time.max, tzinfo=timezone.utc)
        report = discover_parcel(geometry, start, end,
                                 max_cloud_percent=args.max_cloud_percent, limit=args.limit)
        serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        else:
            print(serialized, end="")
        return 0
    except (OSError, ValueError, TypeError, CatalogUnavailable) as exc:
        parser.exit(2, f"SCIM discovery failed: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())

"""CLI for approved, locally staged SCIM scene validation.

No network calls. This command checks operator-supplied SHA-256 checksums and
runs actual local GeoTIFF data through the raster evaluator against a WGS84
parcel GeoJSON. The caller must independently verify scene provenance.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path
from .scim_scene_manifest import StagedSceneManifest
from .scim_raster_preflight import preflight_staged_scene
from .scim_rasterio_pipeline import evaluate_staged_scene
from .scim_reference_comparison import SceneReference, ComparisonTolerance, compare_scene

def _evaluate_verified_scene(root: Path, manifest: StagedSceneManifest,
                             parcel_geometry: dict) -> dict:
    result = evaluate_staged_scene(
        root, manifest.provider, manifest.qa.filename,
        {key: value.filename for key, value in manifest.bands.items()},
        parcel_geometry,
        sentinel_quantification=manifest.sentinel_quantification,
        sentinel_offsets=manifest.sentinel_offsets)
    if result.parcel_pixels == 0 or result.valid_pixels == 0:
        raise ValueError("No valid parcel pixels; review scene, QA and calibration")
    from .scim_staged_worker import _summary
    return _summary(result)

def validate_scene(root: Path, manifest: StagedSceneManifest,
                   parcel_geometry: dict) -> dict:
    """Backward-compatible validated summary."""
    preflight_staged_scene(root, manifest, parcel_geometry)
    return _evaluate_verified_scene(root, manifest, parcel_geometry)

def validate_scene_report(root: Path, manifest: StagedSceneManifest,
                          parcel_geometry: dict) -> dict:
    """Consolidated checksum, preflight and index evaluation report."""
    preflight = preflight_staged_scene(root, manifest, parcel_geometry)
    summary = _evaluate_verified_scene(root, manifest, parcel_geometry)
    return {"scene_id": manifest.scene_id, "preflight": preflight,
            "summary": summary, "reference_comparison": "not_performed",
            "provenance_verified": False}

def write_validation_report(output: Path, report: dict) -> None:
    """Atomically create a new local JSON report; never overwrite an existing report."""
    output = Path(output)
    if output.suffix.lower() != ".json" or output.is_symlink() or output.exists():
        raise ValueError("Output must be a new non-symlink JSON file")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise ValueError("Output directory must exist and must not be a symlink")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=output.parent, prefix=".scim-report-",
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write(chr(10))
            stream.flush()
            os.fsync(stream.fileno())
        # Exclusive creation prevents silently replacing a prior validation artifact.
        with output.open("xb") as target, temporary.open("rb") as source:
            while chunk := source.read(65536):
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description="Validate approved SCIM GeoTIFF scene offline")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--parcel", type=Path, required=True)
    parser.add_argument("--reference", type=Path, help="Independent reference metrics JSON")
    parser.add_argument("--output", type=Path, help="Write new JSON validation report (no overwrite)")
    parser.add_argument("--index-tolerance", type=float, default=0.03)
    parser.add_argument("--pixel-tolerance", type=int, default=0)
    args = parser.parse_args()
    manifest = StagedSceneManifest.model_validate_json(args.manifest.read_text())
    geometry = json.loads(args.parcel.read_text())
    report = validate_scene_report(args.root, manifest, geometry)
    summary = report["summary"]
    if args.reference is not None:
        reference = SceneReference.model_validate_json(args.reference.read_text())
        if reference.scene_id != manifest.scene_id:
            raise ValueError("Reference scene ID does not match manifest")
        comparison = compare_scene(summary, reference, ComparisonTolerance(
            index_absolute=args.index_tolerance, pixel_absolute=args.pixel_tolerance))
        report["reference_comparison"] = comparison
        if args.output:
            write_validation_report(args.output, report)
        print(json.dumps(report, sort_keys=True))
        if not comparison["passed"]:
            raise SystemExit(2)
    else:
        if args.output:
            write_validation_report(args.output, report)
        print(json.dumps(report, sort_keys=True))

if __name__ == "__main__":
    main()

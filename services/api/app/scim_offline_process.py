"""CLI for offline checksum-gated scene cropping and parcel validation."""
import argparse
import json
from pathlib import Path
from .scim_scene_manifest import StagedSceneManifest
from .scim_multiband_extract import extract_staged_scene
from .scim_real_scene_validation import validate_scene_report, write_validation_report

def process_local_scene(root: Path, manifest: StagedSceneManifest,
                        parcel: dict, output_dir: Path, *, margin_pixels: int = 1) -> dict:
    """Produce cropped rasters, manifest and validation report in an empty directory."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir() or output_dir.is_symlink() or any(output_dir.iterdir()):
        raise ValueError("Output directory must exist, be real, and be empty")
    try:
        extracted = extract_staged_scene(root, manifest, parcel, output_dir,
                                         margin_pixels=margin_pixels)
        cropped_manifest = StagedSceneManifest.model_validate(extracted["manifest"])
        report = validate_scene_report(output_dir, cropped_manifest, parcel)
        report["extraction"] = {
            "source_manifest_checksum_verified": extracted["source_manifest_checksum_verified"],
            "output_checksum_verified": extracted["output_checksum_verified"],
            "network_access": False, "provenance_verified": False}
        write_validation_report(output_dir / "validation-report.json", report)
        write_validation_report(output_dir / "cropped-manifest.json",
                                cropped_manifest.model_dump(mode="json"))
        return report
    except Exception:
        # Output directory must have been empty at entry; remove only generated files.
        for name in ("qa.tif", "validation-report.json", "cropped-manifest.json",
                     *(key + ".tif" for key in manifest.bands)):
            path = output_dir / name
            if path.is_file() and not path.is_symlink():
                path.unlink()
        raise

def main() -> int:
    parser = argparse.ArgumentParser(description="Offline SCIM crop and validate approved scene")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--parcel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--margin-pixels", type=int, default=1)
    args = parser.parse_args()
    try:
        manifest = StagedSceneManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
        parcel = json.loads(args.parcel.read_text(encoding="utf-8"))
        report = process_local_scene(args.root, manifest, parcel, args.output_dir,
                                     margin_pixels=args.margin_pixels)
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, f"SCIM offline processing failed: {exc}" + chr(10))
    print(json.dumps(report, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

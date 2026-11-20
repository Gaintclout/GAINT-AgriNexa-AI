"""Offline multi-band parcel cropping with verified source manifest.

Input checksums prove byte consistency with the supplied manifest, not
independent satellite provenance. Output must be a separate empty directory.
"""
from pathlib import Path
from .scim_scene_manifest import StagedSceneManifest, verify_staged_manifest
from .scim_cog_local_extract import extract_local_parcel_window

def extract_staged_scene(root: Path, manifest: StagedSceneManifest,
                         parcel_geometry: dict, output_dir: Path,
                         *, margin_pixels: int = 1) -> dict:
    """Crop all required scene bands; return a new checksummed scene manifest."""
    root = Path(root)
    output_dir = Path(output_dir)
    if (not output_dir.is_dir() or output_dir.is_symlink()
            or any(output_dir.iterdir())
            or output_dir.resolve() == root.resolve()):
        raise ValueError("Output must be a separate empty real directory")
    # Verify every original asset before creating any cropped outputs.
    verify_staged_manifest(root, manifest)
    items = [("qa", manifest.qa), *sorted(manifest.bands.items())]
    created = []
    cropped = {}
    try:
        for key, item in items:
            destination = output_dir / (key + ".tif")
            report = extract_local_parcel_window(
                root, item.filename, parcel_geometry, destination,
                margin_pixels=margin_pixels)
            created.append(destination)
            cropped[key] = {"filename": destination.name, "sha256": report["sha256"]}
        new_manifest = StagedSceneManifest(
            provider=manifest.provider, scene_id=manifest.scene_id,
            qa=cropped.pop("qa"), bands=cropped,
            sentinel_quantification=manifest.sentinel_quantification,
            sentinel_offsets=manifest.sentinel_offsets)
        verify_staged_manifest(output_dir, new_manifest)
        return {"manifest": new_manifest.model_dump(mode="json"),
                "output_checksum_verified": True,
                "source_manifest_checksum_verified": True,
                "provenance_verified": False, "network_access": False}
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise

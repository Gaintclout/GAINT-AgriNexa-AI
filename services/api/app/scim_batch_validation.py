"""Offline multi-scene SCIM validation runner.

Inputs must be operator-approved local files. This utility does not fetch
imagery, authenticate satellite provenance, or authorize production rollout.
"""
import argparse
import json
from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from .scim_scene_manifest import StagedSceneManifest
from .scim_reference_comparison import SceneReference, ComparisonTolerance, compare_scene
from .scim_real_scene_validation import validate_scene

class SceneCase(BaseModel):
    root: Path
    manifest: Path
    parcel: Path
    reference: Path

class ValidationBatch(BaseModel):
    cases: list[SceneCase] = Field(min_length=2, max_length=20)

def validate_batch(batch: ValidationBatch, tolerance: ComparisonTolerance | None = None) -> dict:
    """Compare all supplied scenes and require Sentinel-2 plus Landsat evidence."""
    reports = []
    providers = set()
    seen_scenes = set()
    for case in batch.cases:
        manifest = StagedSceneManifest.model_validate_json(case.manifest.read_text())
        reference = SceneReference.model_validate_json(case.reference.read_text())
        if manifest.scene_id != reference.scene_id:
            raise ValueError("Reference scene ID does not match manifest")
        scene_key = (manifest.provider.value, manifest.scene_id)
        if scene_key in seen_scenes:
            raise ValueError("Duplicate satellite scene in validation batch")
        seen_scenes.add(scene_key)
        polygon = json.loads(case.parcel.read_text())
        summary = validate_scene(case.root, manifest, polygon)
        comparison = compare_scene(summary, reference, tolerance)
        reports.append({"provider": manifest.provider.value, "scene_id": manifest.scene_id,
                        "summary": summary, "comparison": comparison})
        if comparison["passed"]:
            providers.add(manifest.provider.value)
    coverage = {"sentinel_2": "sentinel-2" in providers,
                "landsat": bool(providers.intersection({"landsat-8", "landsat-9"}))}
    return {"passed": all(coverage.values()) and all(
                item["comparison"]["passed"] for item in reports),
            "coverage": coverage, "scenes": reports,
            "status": "offline_reference_comparison_only"}

def main():
    parser = argparse.ArgumentParser(description="Validate staged Sentinel-2 and Landsat scenes")
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    batch = ValidationBatch.model_validate_json(args.batch.read_text())
    result = validate_batch(batch)
    report = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(report + "\n")
    else:
        print(report)
    if not result["passed"]:
        raise SystemExit(2)

if __name__ == "__main__":
    main()

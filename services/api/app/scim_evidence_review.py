"""SCIM Phase 1 evidence readiness check. No automatic deployment approval."""

def assess_evidence(evidence: dict) -> dict:
    required = ("api_ci", "postgis_ci", "web_ci", "worker_review")
    checks = {key: evidence.get(key) is True for key in required}
    scenes = evidence.get("scenes")
    scenes = scenes if isinstance(scenes, list) else []
    passed = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        if (scene.get("comparison_passed") is True
                and scene.get("provenance_reviewed") is True
                and scene.get("cloud_mask_reviewed") is True
                and scene.get("parcel_clipping_reviewed") is True):
            passed.add(scene.get("provider"))
    checks["sentinel_2"] = "sentinel-2" in passed
    checks["landsat"] = bool(passed.intersection({"landsat-8", "landsat-9"}))
    return {"checks": checks, "ready_for_review": all(checks.values())}

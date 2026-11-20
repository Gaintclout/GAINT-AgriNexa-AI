"""SCIM Phase 1 review report from operator evidence and batch validation.

Does not authenticate satellite provenance or authorize production deployment.
"""
import argparse
import json
from pathlib import Path
from .scim_evidence_review import assess_evidence

def build_review(batch_report: dict, operator_evidence: dict) -> dict:
    if not isinstance(batch_report, dict) or not isinstance(operator_evidence, dict):
        raise ValueError("Review inputs must be JSON objects")
    scenes = batch_report.get("scenes")
    if not isinstance(scenes, list) or not batch_report.get("passed") is True:
        return {"ready_for_review": False, "reason": "Satellite batch validation has not passed"}
    reviewed = operator_evidence.get("scenes")
    if not isinstance(reviewed, list):
        reviewed = []
    matched = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        if scene.get("comparison", {}).get("passed") is not True:
            continue
        matches = [item for item in reviewed if isinstance(item, dict)
                   and item.get("provider") == scene.get("provider")
                   and item.get("scene_id") == scene.get("scene_id")]
        if len(matches) != 1:
            continue
        matched.append({**matches[0], "comparison_passed": True})
    evidence = {key: operator_evidence.get(key) for key in
                ("api_ci", "postgis_ci", "web_ci", "worker_review")}
    evidence["scenes"] = matched
    outcome = assess_evidence(evidence)
    return {"ready_for_review": outcome["ready_for_review"],
            "checks": outcome["checks"], "matched_scene_count": len(matched),
            "status": "operator_evidence_review_only"}

def main():
    parser = argparse.ArgumentParser(description="Review SCIM Phase 1 evidence")
    parser.add_argument("--batch-report", type=Path, required=True)
    parser.add_argument("--operator-evidence", type=Path, required=True)
    args = parser.parse_args()
    result = build_review(json.loads(args.batch_report.read_text()),
                          json.loads(args.operator_evidence.read_text()))
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ready_for_review"]:
        raise SystemExit(2)

if __name__ == "__main__":
    main()

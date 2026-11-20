"""Phase 1 report matching tests."""
from app.scim_phase1_review import build_review

def inputs():
    scenes = [{"provider": "sentinel-2", "scene_id": "S2-A",
               "comparison": {"passed": True}},
              {"provider": "landsat-8", "scene_id": "L8-A",
               "comparison": {"passed": True}}]
    evidence = {"api_ci": True, "postgis_ci": True, "web_ci": True,
                "worker_review": True,
                "scenes": [{"provider": s["provider"], "scene_id": s["scene_id"],
                            "provenance_reviewed": True, "cloud_mask_reviewed": True,
                            "parcel_clipping_reviewed": True} for s in scenes]}
    return {"passed": True, "scenes": scenes}, evidence

def test_matching_two_sensor_evidence_ready_for_review():
    batch, evidence = inputs()
    result = build_review(batch, evidence)
    assert result["ready_for_review"]
    assert result["matched_scene_count"] == 2

def test_unmatched_scene_cannot_be_approved():
    batch, evidence = inputs()
    evidence["scenes"][1]["scene_id"] = "unrelated"
    assert not build_review(batch, evidence)["ready_for_review"]

def test_duplicate_operator_review_is_rejected():
    batch, evidence = inputs()
    evidence["scenes"].append(dict(evidence["scenes"][0]))
    assert not build_review(batch, evidence)["ready_for_review"]

def test_failed_batch_never_ready():
    batch, evidence = inputs()
    batch["passed"] = False
    assert not build_review(batch, evidence)["ready_for_review"]

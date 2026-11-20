"""SCIM Phase 1 evidence checklist regression tests."""
from app.scim_evidence_review import assess_evidence

def evidence():
    scene = dict(comparison_passed=True, provenance_reviewed=True,
                 cloud_mask_reviewed=True, parcel_clipping_reviewed=True)
    return dict(api_ci=True, postgis_ci=True, web_ci=True, worker_review=True,
                scenes=[dict(scene, provider="sentinel-2"),
                        dict(scene, provider="landsat-8")])

def test_both_sensor_families_and_ci_required():
    assert assess_evidence(evidence())["ready_for_review"]

def test_missing_landsat_blocks_readiness():
    data = evidence()
    data["scenes"] = data["scenes"][:1]
    result = assess_evidence(data)
    assert not result["ready_for_review"]
    assert not result["checks"]["landsat"]

def test_unreviewed_provenance_blocks_readiness():
    data = evidence()
    data["scenes"][1]["provenance_reviewed"] = False
    assert not assess_evidence(data)["ready_for_review"]

def test_ci_failure_blocks_readiness():
    data = evidence()
    data["postgis_ci"] = False
    assert not assess_evidence(data)["ready_for_review"]

def test_missing_scene_list_fails_closed():
    data = evidence()
    data["scenes"] = None
    assert not assess_evidence(data)["ready_for_review"]

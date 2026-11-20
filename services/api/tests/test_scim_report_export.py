import json
import pytest
from app.scim_real_scene_validation import write_validation_report

def test_report_export(tmp_path):
    path = tmp_path / "report.json"
    write_validation_report(path, {"passed": True})
    assert json.loads(path.read_text()) == {"passed": True}
    with pytest.raises(ValueError):
        write_validation_report(path, {"passed": False})
    assert json.loads(path.read_text()) == {"passed": True}

def test_bad_report_rejected(tmp_path):
    path = tmp_path / "report.json"
    with pytest.raises(ValueError):
        write_validation_report(path, {"value": float("nan")})
    assert not path.exists()

import pytest
from pydantic import ValidationError
from app.main import app
from app.scim_indices import ReflectanceSample, calculate_indices

def test_vegetation_and_moisture_indices():
    result = calculate_indices(ReflectanceSample(red=0.2,nir=0.6,green=0.3,swir1=0.4))
    assert result.ndvi == 0.5
    assert result.ndwi == pytest.approx(-0.333333,abs=1e-6)
    assert result.ndmi == 0.2

def test_zero_denominator_is_missing_not_zero():
    result = calculate_indices(ReflectanceSample(red=0,nir=0,green=0,swir1=0))
    assert result.ndvi is None
    assert result.ndwi is None
    assert result.ndmi is None

@pytest.mark.parametrize("value",[-0.01,1.01,float("inf"),float("nan")])
def test_invalid_reflectance_rejected(value):
    with pytest.raises(ValidationError):
        ReflectanceSample(red=value,nir=0.5,green=0.5,swir1=0.5)

def test_scim_indices_route_documented():
    operation = app.openapi()["paths"]["/api/v1/scim/indices/calculate"]["post"]
    assert operation["tags"] == ["scim"]

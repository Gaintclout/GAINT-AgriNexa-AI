import pytest
from pydantic import ValidationError
from app.scim_bands import SensorBandSample, calculate_sensor_indices
from app.main import app

@pytest.mark.parametrize("provider,bands",[
    ("sentinel-2",{"B04":0.2,"B08":0.6,"B03":0.3,"B11":0.4}),
    ("landsat-8",{"SR_B4":0.2,"SR_B5":0.6,"SR_B3":0.3,"SR_B6":0.4}),
    ("landsat-9",{"SR_B4":0.2,"SR_B5":0.6,"SR_B3":0.3,"SR_B6":0.4}),
])
def test_sensor_mapping(provider,bands):
    assert calculate_sensor_indices(SensorBandSample(provider=provider,bands=bands)).ndvi == 0.5

def test_missing_band_rejected():
    with pytest.raises(ValidationError):
        SensorBandSample(provider="sentinel-2",bands={"B04":0.2,"B08":0.6,"B03":0.3,"other":0.4})

def test_sensor_endpoint_documented():
    assert "/api/v1/scim/indices/from-bands" in app.openapi()["paths"]

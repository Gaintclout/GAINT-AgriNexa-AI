import pytest
from pydantic import ValidationError
from app.scim_parcel_summary import ParcelSummaryRequest, summarize_parcel
from app.main import app

def sample(clear=True, red=0.2, nir=0.6, green=0.3, swir1=0.4, parcel="P-1"):
    return {"parcel_id":parcel,"scene_id":"S-1","clear_pixel":clear,
            "reflectance":{"red":red,"nir":nir,"green":green,"swir1":swir1}}

def test_parcel_median_indices_and_cloud_mask():
    request=ParcelSummaryRequest(parcel_id="P-1",samples=[
        sample(),sample(clear=False,red=0.8,nir=0.1),sample(red=0.3,nir=0.5,green=0.3,swir1=0.3)])
    result=summarize_parcel(request)
    assert result.total_samples == 3
    assert result.clear_samples == 2
    assert result.valid_samples == 2
    assert result.ndvi_median == 0.375

def test_no_clear_pixels_returns_missing_indices():
    result=summarize_parcel(ParcelSummaryRequest(parcel_id="P-1",samples=[sample(clear=False)]))
    assert result.ndvi_median is None
    assert result.valid_samples == 0

def test_zero_denominators_are_not_valid_pixels():
    result=summarize_parcel(ParcelSummaryRequest(parcel_id="P-1",samples=[sample(red=0,nir=0,green=0,swir1=0)]))
    assert result.clear_samples == 1
    assert result.valid_samples == 0
    assert result.ndwi_median is None

def test_cross_parcel_samples_rejected():
    with pytest.raises(ValidationError):
        ParcelSummaryRequest(parcel_id="P-1",samples=[sample(parcel="P-2")])

def test_summary_route_documented():
    assert "/api/v1/scim/parcels/summarize-samples" in app.openapi()["paths"]

def test_processing_stages_are_exposed_in_openapi():
    assert '/api/v1/scim/processing/stages' in app.openapi()['paths']

def test_processing_stages_are_ordered():
    from app.scim_processing_stages import processing_stages
    assert processing_stages() == ['verify_scene','resolve_assets','calibrate_reflectance','mask_clouds','clip_to_parcel','summarize_indices']

def test_processing_preview_registered():
    assert '/api/v1/scim/processing/preview' in app.openapi()['paths']

def test_plan_rejects_missing_bands():
    from datetime import datetime, timezone
    from app.scim_plan import PlanRequest
    with pytest.raises(ValidationError):
        PlanRequest(provider="sentinel-2",parcel_id="P1",scene_id="S1",
                    captured_at=datetime(2026,9,1,tzinfo=timezone.utc),
                    available_bands=["red"],cloud_cover_percent=12)

def test_plan_rejects_future_timestamp():
    from datetime import datetime, timedelta, timezone
    from app.scim_plan import PlanRequest
    with pytest.raises(ValidationError):
        PlanRequest(provider="sentinel-2",parcel_id="P1",scene_id="S1",
                    captured_at=datetime.now(timezone.utc)+timedelta(days=1),
                    available_bands=["red","green","nir","swir16"],cloud_cover_percent=12)

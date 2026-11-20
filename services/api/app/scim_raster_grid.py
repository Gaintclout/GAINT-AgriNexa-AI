"""Bounded in-memory raster grid evaluation with strict co-registration checks.

Grid data must come from trusted raster decoding. The caller-provided parcel mask
is NOT geospatially verified here; PostGIS/rasterio clipping is still required.
No network access, filesystem access, resampling or persistence.
"""
from math import isfinite
from pydantic import BaseModel, Field, model_validator
from .scim_bands import BAND_MAP
from .scim_contracts import SatelliteProvider
from .scim_raw_pixel import RawPixelInput, evaluate_raw_pixel

MAX_PIXELS = 10000

class RasterGrid(BaseModel):
    width: int = Field(ge=1, le=100)
    height: int = Field(ge=1, le=100)
    crs: str = Field(min_length=1, max_length=100)
    transform: tuple[float, float, float, float, float, float]
    values: list[int]

    @model_validator(mode="after")
    def valid_grid(self):
        if self.width * self.height > MAX_PIXELS or len(self.values) != self.width * self.height:
            raise ValueError("Raster dimensions and data length must match within pixel limit")
        if not all(isfinite(v) for v in self.transform):
            raise ValueError("Nonfinite raster transform")
        if any(not 0 <= v <= 65535 for v in self.values):
            raise ValueError("Raster digital numbers must be uint16")
        return self

class RasterEvaluationRequest(BaseModel):
    provider: SatelliteProvider
    qa: RasterGrid
    bands: dict[str, RasterGrid]
    parcel_mask: list[bool]
    sentinel_quantification: float | None = None
    sentinel_offsets: dict[str, float] | None = None

    @model_validator(mode="after")
    def co_registered(self):
        required = set(BAND_MAP[self.provider].values())
        if set(self.bands) != required:
            raise ValueError("Exactly the required sensor bands must be supplied")
        if len(self.parcel_mask) != self.qa.width * self.qa.height:
            raise ValueError("Parcel mask size mismatch")
        for band in self.bands.values():
            if (band.width, band.height, band.crs, band.transform) != (
                self.qa.width, self.qa.height, self.qa.crs, self.qa.transform
            ):
                raise ValueError("Raster bands and QA must be co-registered")
        return self

class RasterEvaluationResult(BaseModel):
    parcel_pixels: int
    clear_pixels: int
    valid_pixels: int
    ndvi_values: list[float]
    ndwi_values: list[float]
    ndmi_values: list[float]

def evaluate_raster_grid(request: RasterEvaluationRequest) -> RasterEvaluationResult:
    from .scim_calibration import CalibrationInput
    from .scim_cloud_mask import PixelQuality, QualitySensor, is_clear_pixel
    parcel = clear = valid = 0
    ndvi, ndwi, ndmi = [], [], []
    for index, inside in enumerate(request.parcel_mask):
        if not inside:
            continue
        parcel += 1
        qa = request.qa.values[index]
        if not is_clear_pixel(PixelQuality(sensor=QualitySensor(request.provider.value), qa_value=qa)):
            continue
        clear += 1
        calibration = CalibrationInput(
            provider=request.provider,
            digital_numbers={key: grid.values[index] for key, grid in request.bands.items()},
            sentinel_quantification=request.sentinel_quantification,
            sentinel_offsets=request.sentinel_offsets,
        )
        try:
            result = evaluate_raw_pixel(RawPixelInput(
                provider=request.provider, qa_value=qa, calibration=calibration))
        except (ValueError, ArithmeticError):
            continue
        if result.indices is None or any(
            getattr(result.indices, key) is None for key in ("ndvi", "ndwi", "ndmi")
        ):
            continue
        valid += 1
        ndvi.append(result.indices.ndvi)
        ndwi.append(result.indices.ndwi)
        ndmi.append(result.indices.ndmi)
    return RasterEvaluationResult(parcel_pixels=parcel, clear_pixels=clear,
        valid_pixels=valid, ndvi_values=ndvi, ndwi_values=ndwi, ndmi_values=ndmi)

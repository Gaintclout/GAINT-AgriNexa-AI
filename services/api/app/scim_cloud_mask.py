"""Sensor-specific pixel quality screening for SCIM.

Inputs are decoded integer QA values from trusted raster data, not raw imagery.
A clear pixel is not a guarantee of usable reflectance or parcel membership.
"""
from enum import Enum
from pydantic import BaseModel, Field

class QualitySensor(str, Enum):
    sentinel_2 = "sentinel-2"
    landsat_8 = "landsat-8"
    landsat_9 = "landsat-9"

class PixelQuality(BaseModel):
    sensor: QualitySensor
    qa_value: int = Field(ge=0, le=65535)

def is_clear_pixel(sample: PixelQuality) -> bool:
    qa = sample.qa_value
    if sample.sensor == QualitySensor.sentinel_2:
        # Sentinel-2 L2A SCL: vegetation (4), bare soils (5), water (6).
        # Reject no-data, shadows, clouds, cirrus, snow, and unclassified.
        return qa in (4, 5, 6)
    # Landsat Collection 2 QA_PIXEL:
    # bits 0 fill, 1 dilated cloud, 2 cirrus, 3 cloud,
    # 4 cloud shadow, 5 snow. Also reject water? No: water remains valid.
    return (qa & 0b111111) == 0

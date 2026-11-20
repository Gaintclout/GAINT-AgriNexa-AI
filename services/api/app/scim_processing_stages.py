"""Define satellite processing stages without executing jobs."""
from enum import Enum

class ProcessingStage(str, Enum):
    verify_scene = "verify_scene"
    resolve_assets = "resolve_assets"
    calibrate_reflectance = "calibrate_reflectance"
    mask_clouds = "mask_clouds"
    clip_to_parcel = "clip_to_parcel"
    summarize_indices = "summarize_indices"

def processing_stages() -> list[str]:
    return [stage.value for stage in ProcessingStage]

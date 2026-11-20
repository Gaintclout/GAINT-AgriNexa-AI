"""Offline SCIM scene manifest validation for operator-approved staged imagery.

This is a metadata gate, not independent verification of satellite provenance.
Never infer a checksum from untrusted STAC metadata or fetch arbitrary URLs.
"""
from pathlib import Path
from hashlib import sha256
from pydantic import BaseModel, Field, model_validator
from .scim_bands import BAND_MAP
from .scim_contracts import SatelliteProvider
from .scim_rasterio_pipeline import _trusted_path

class StagedBand(BaseModel):
    filename: str = Field(min_length=1, max_length=160)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

class StagedSceneManifest(BaseModel):
    provider: SatelliteProvider
    scene_id: str = Field(min_length=1, max_length=256)
    qa: StagedBand
    bands: dict[str, StagedBand]
    sentinel_quantification: float | None = None
    sentinel_offsets: dict[str, float] | None = None

    @model_validator(mode="after")
    def required_bands(self):
        if set(self.bands) != set(BAND_MAP[self.provider].values()):
            raise ValueError("Scene manifest must include exactly required sensor bands")
        filenames = [self.qa.filename, *(item.filename for item in self.bands.values())]
        if len(filenames) != len(set(filenames)):
            raise ValueError("Scene manifest must not reuse a raster file")
        return self

def verify_staged_manifest(root: Path, manifest: StagedSceneManifest) -> dict[str, str]:
    """Verify all local files against independently approved checksums."""
    paths = {}
    for band, item in [("qa", manifest.qa), *manifest.bands.items()]:
        path = _trusted_path(root, item.filename)
        digest = sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != item.sha256.lower():
            raise ValueError("Staged raster checksum mismatch")
        paths[band] = str(path)
    return paths

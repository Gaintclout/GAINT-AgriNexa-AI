"""Read-only STAC discovery via a fixed public Earth Search endpoint.

No arbitrary user-provided URLs, redirects, asset downloads or persistence.
"""
import json
from datetime import datetime
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from pydantic import BaseModel, Field, ValidationError, field_validator
from .scim_catalog import CatalogSearch, build_stac_search
from .scim_contracts import SatelliteProvider
from .scim_asset_review import review_assets

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"
MAX_RESPONSE_BYTES = 1_000_000

class CatalogUnavailable(Exception):
    pass

class DiscoveredScene(BaseModel):
    scene_id: str = Field(min_length=1, max_length=200)
    collection: str
    captured_at: datetime
    cloud_cover_percent: float | None = Field(default=None, ge=0, le=100)
    bbox: tuple[float, float, float, float]
    available_bands: list[str] = Field(default_factory=list)
    missing_bands: list[str] = Field(default_factory=list)
    assets_complete: bool = False

    @field_validator("captured_at")
    @classmethod
    def aware_capture(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("STAC acquisition timestamp requires timezone")
        return value

    @field_validator("bbox")
    @classmethod
    def valid_bbox(cls, value):
        west, south, east, north = value
        if not all(isfinite(v) for v in value) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Invalid STAC WGS84 bounds")
        return value


class CatalogResults(BaseModel):
    scenes: list[DiscoveredScene]
    returned: int
    truncated: bool

class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

def parse_stac_response(payload: dict, search: CatalogSearch) -> CatalogResults:
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise CatalogUnavailable("Invalid STAC feature collection")
    features = payload["features"]
    if len(features) > search.limit:
        raise CatalogUnavailable("Catalog returned more features than requested")
    scenes = []
    for feature in features:
        if not isinstance(feature, dict):
            raise CatalogUnavailable("Invalid STAC feature")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise CatalogUnavailable("Missing STAC properties")
        try:
            scene = DiscoveredScene(
                scene_id=feature["id"], collection=feature["collection"],
                captured_at=properties["datetime"], cloud_cover_percent=properties.get("eo:cloud_cover"),
                bbox=feature["bbox"],
            )
        except (KeyError, TypeError, ValidationError, ValueError) as exc:
            raise CatalogUnavailable("Invalid STAC scene metadata") from exc
        if scene.collection != build_stac_search(search)["collections"][0]:
            continue
        if search.provider == SatelliteProvider.landsat_8 and properties.get("platform") != "landsat-8":
            continue
        if search.provider == SatelliteProvider.landsat_9 and properties.get("platform") != "landsat-9":
            continue
        if not search.start <= scene.captured_at <= search.end:
            continue
        if scene.cloud_cover_percent is None or scene.cloud_cover_percent > search.max_cloud_percent:
            continue
        try:
            assessment = review_assets(search.provider, feature.get('assets', {}))
        except ValueError as exc:
            raise CatalogUnavailable("Invalid STAC asset metadata") from exc
        scenes.append(scene.model_copy(update={
            'available_bands': assessment['available_bands'],
            'missing_bands': assessment['missing_bands'],
            'assets_complete': assessment['complete'],
        }))
    return CatalogResults(scenes=scenes, returned=len(scenes), truncated=bool(payload.get("links") and any(
        isinstance(link, dict) and link.get("rel") == "next" for link in payload["links"]
    )))

def discover_scenes(search: CatalogSearch) -> CatalogResults:
    body = json.dumps(build_stac_search(search)).encode("utf-8")
    request = Request(EARTH_SEARCH_URL, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/geo+json", "User-Agent": "GAINT-AgriNexa-SCIM/0.1"
    }, method="POST")
    opener = build_opener(NoRedirects())
    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise CatalogUnavailable("Satellite catalog returned an error")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CatalogUnavailable("Satellite catalog is temporarily unavailable") from exc
    if len(raw) > MAX_RESPONSE_BYTES:
        raise CatalogUnavailable("Satellite catalog response exceeds size limit")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise CatalogUnavailable("Invalid satellite catalog response") from exc
    return parse_stac_response(payload, search)

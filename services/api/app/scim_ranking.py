"""SCIM quality ranking for read-only scene discovery."""
from datetime import timezone
from .scim_discovery import CatalogResults, DiscoveredScene

def rank_scenes(results: CatalogResults) -> list[DiscoveredScene]:
    """Prefer scenes with all required bands, lower cloud cover and recent acquisition."""
    return sorted(results.scenes, key=lambda scene: (
        not scene.assets_complete,
        scene.cloud_cover_percent if scene.cloud_cover_percent is not None else 101,
        -scene.captured_at.astimezone(timezone.utc).timestamp(),
        scene.scene_id,
    ))

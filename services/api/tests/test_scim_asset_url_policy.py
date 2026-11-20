"""Security tests for STAC asset URL policy."""
import pytest
from app.scim_asset_url_policy import validate_asset_url

def test_allowed_bucket_object():
    url = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/tiles/scene/B04.tif"
    assert validate_asset_url(url) == url

@pytest.mark.parametrize("url", [
    "http://sentinel-cogs.s3.us-west-2.amazonaws.com/a.tif",
    "https://127.0.0.1/a.tif",
    "https://localhost/a.tif",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com.evil.test/a.tif",
    "https://user:pass@sentinel-cogs.s3.us-west-2.amazonaws.com/a.tif",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com:8443/a.tif",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a.tif#part",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a.tif\n",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a/../secret.tif",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a/%2e%2e/secret.tif",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a/%0a/secret.tif",
    "https://sentinel-cogs.s3.us-west-2.amazonaws.com/a/%5csecret.tif",
    "file:///etc/passwd",
    "",
])
def test_reject_untrusted_urls(url):
    with pytest.raises(ValueError):
        validate_asset_url(url)

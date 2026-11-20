"""Fail-closed STAC asset URL validation; does not download imagery.

Only HTTPS objects hosted on explicitly trusted public data buckets are eligible.
A valid URL is not proof of scene authenticity or safe image contents.
"""
from urllib.parse import urlsplit, unquote
from ipaddress import ip_address

TRUSTED_HOSTS = frozenset({
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    "sentinel-s2-l2a-cogs.s3.amazonaws.com",
    "usgs-landsat.s3.us-west-2.amazonaws.com",
})

def validate_asset_url(url: str) -> str:
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise ValueError("Invalid asset URL")
    if any(ord(char) < 33 or ord(char) == 127 for char in url):
        raise ValueError("Asset URL contains whitespace or controls")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Malformed asset URL") from exc
    if (parsed.scheme != "https" or not host or host not in TRUSTED_HOSTS
            or parsed.username is not None or parsed.password is not None
            or port not in (None, 443) or not parsed.path.startswith("/")
            or parsed.path == "/" or parsed.fragment):
        raise ValueError("Untrusted asset URL")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not allowed")
    # Do not allow encoded path separators or traversal to bypass object-prefix checks.
    decoded = unquote(parsed.path)
    if (not decoded.startswith("/") or chr(92) in decoded or
            any(segment in (".", "..") for segment in decoded.split("/")) or
            any(ord(char) < 33 or ord(char) == 127 for char in decoded)):
        raise ValueError("Unsafe asset object path")
    return url

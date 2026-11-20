import pytest
from app.scim_cog_object_version import validate_object_version
from app.scim_cog_range_fetch import RangeFetchError

def test_initial_etag_not_yet_pinned():
    result=validate_object_version({"ETag":'"version-1"'})
    assert result["etag"]=='"version-1"'
    assert result["object_version_pinned"] is False
    assert result["source_checksum_verified"] is False

def test_matching_expected_etag():
    result=validate_object_version({"ETag":'"version-1"'},
                                   expected_etag='"version-1"')
    assert result["object_version_pinned"] is True

@pytest.mark.parametrize("headers",[
    {},{"ETag":'W/"weak"'},{"ETag":"unquoted"},
    {"ETag":'""'},{"ETag":'"valid"',"Content-Encoding":"gzip"}])
def test_invalid_version_headers(headers):
    with pytest.raises(RangeFetchError):
        validate_object_version(headers)

def test_changed_etag():
    with pytest.raises(RangeFetchError,match="changed"):
        validate_object_version({"ETag":'"new"'},expected_etag='"old"')

def test_invalid_expected_checksum():
    with pytest.raises(RangeFetchError,match="SHA256"):
        validate_object_version({"ETag":'"version-1"'},expected_sha256="xyz")

def test_expected_checksum_does_not_verify_content():
    result=validate_object_version({"ETag":'"version-1"'},
                                   expected_sha256="a"*64)
    assert result["source_checksum_verified"] is False

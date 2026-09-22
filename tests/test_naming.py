from openapi_client_codegen.naming import DefaultNamingPolicy


def test_default_naming_derives_all_variants():
    naming = DefaultNamingPolicy("placeframe")("docker/api")

    assert naming.base == "api-client"
    assert naming.dashed == "placeframe-api-client"
    assert naming.underscored == "placeframe_api_client"
    assert naming.camel == "PlaceframeApiClient"


def test_default_naming_uses_last_path_segment():
    naming = DefaultNamingPolicy("placeframe")("docker/lease-server")

    assert naming.base == "lease-server-client"
    assert naming.dashed == "placeframe-lease-server-client"
    assert naming.underscored == "placeframe_lease_server_client"
    assert naming.camel == "PlaceframeLeaseServerClient"

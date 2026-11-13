import json

import httpx
import pytest

from ifec_ingest.blizzard import SourceError, fetch_commodities, get_token
from ifec_ingest.config import ApiConfig

API = ApiConfig(
    oauth_url="https://oauth.battle.net/token",
    base_url="https://eu.api.blizzard.com",
    namespace="dynamic-forever-eu",
    ruleset_id=2,
)
LAST_MODIFIED = "Fri, 13 Nov 2026 14:22:31 GMT"
BODY = json.dumps(
    {"auctions": [{"id": 1, "item": {"id": 2681}, "quantity": 1, "unit_price": 10142}]}
)


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_get_token_uses_client_credentials():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "tok123", "token_type": "bearer"})

    token = get_token(client_for(handler), API, "my-id", "my-secret")

    assert token == "tok123"
    assert seen["auth"].startswith("Basic ")
    assert seen["body"] == "grant_type=client_credentials"


def test_get_token_failure_raises_source_error():
    with pytest.raises(SourceError, match="401"):
        get_token(client_for(lambda r: httpx.Response(401)), API, "id", "bad")


def test_fetch_returns_body_and_last_modified():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["ims"] = request.headers.get("if-modified-since")
        return httpx.Response(200, content=BODY, headers={"Last-Modified": LAST_MODIFIED})

    result = fetch_commodities(client_for(handler), API, 111, "tok", if_modified_since=None)

    assert result.status == "ok"
    assert result.body == BODY.encode()
    assert result.last_modified == LAST_MODIFIED
    assert seen["url"] == (
        "https://eu.api.blizzard.com/data/wow/ruleset/2/auctions/111/commodities"
        "?namespace=dynamic-forever-eu"
    )
    assert seen["auth"] == "Bearer tok"
    assert seen["ims"] is None


def test_fetch_sends_if_modified_since_and_handles_304():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ims"] = request.headers.get("if-modified-since")
        return httpx.Response(304)

    result = fetch_commodities(
        client_for(handler), API, 111, "tok", if_modified_since=LAST_MODIFIED
    )

    assert seen["ims"] == LAST_MODIFIED
    assert result.status == "not_modified"
    assert result.body is None


@pytest.mark.parametrize("code", [403, 404])
def test_fetch_treats_403_and_404_as_source_unavailable(code):
    result = fetch_commodities(client_for(lambda r: httpx.Response(code)), API, 111, "tok", None)

    assert result.status == "unavailable"
    assert result.http_status == code


@pytest.mark.parametrize("code", [429, 500, 503])
def test_fetch_raises_on_other_errors(code):
    with pytest.raises(SourceError, match=str(code)):
        fetch_commodities(client_for(lambda r: httpx.Response(code)), API, 111, "tok", None)


@pytest.mark.parametrize("content", [b"not json", b'{"something": "else"}', b'{"auctions": "x"}'])
def test_fetch_rejects_body_without_auctions_list(content):
    handler = lambda r: httpx.Response(200, content=content)  # noqa: E731

    with pytest.raises(SourceError, match="unexpected response body"):
        fetch_commodities(client_for(handler), API, 111, "tok", None)

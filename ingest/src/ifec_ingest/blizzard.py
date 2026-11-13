"""Minimal Blizzard Game Data API client for Forever commodities snapshots."""

import json
from dataclasses import dataclass
from typing import Literal

import httpx

from ifec_ingest.config import ApiConfig

# 403/404 mean "the namespace or house is not served (yet)". That is a monitored,
# normal state (e.g. on launch day), not a crash.
UNAVAILABLE_CODES = {403, 404}


class SourceError(RuntimeError):
    """The Blizzard API returned an error or an unexpected response."""


@dataclass(frozen=True)
class FetchResult:
    status: Literal["ok", "not_modified", "unavailable"]
    http_status: int
    body: bytes | None = None
    last_modified: str | None = None


def get_token(client: httpx.Client, api: ApiConfig, client_id: str, client_secret: str) -> str:
    response = client.post(
        api.oauth_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
    )
    if response.status_code != 200:
        raise SourceError(f"token request failed: HTTP {response.status_code}")
    return response.json()["access_token"]


def commodities_url(api: ApiConfig, house_id: int) -> str:
    return f"{api.base_url}/data/wow/ruleset/{api.ruleset_id}/auctions/{house_id}/commodities"


def fetch_commodities(
    client: httpx.Client,
    api: ApiConfig,
    house_id: int,
    token: str,
    if_modified_since: str | None,
) -> FetchResult:
    headers = {"Authorization": f"Bearer {token}"}
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since

    response = client.get(
        commodities_url(api, house_id), params={"namespace": api.namespace}, headers=headers
    )
    code = response.status_code

    if code == 304:
        return FetchResult(status="not_modified", http_status=code)
    if code in UNAVAILABLE_CODES:
        return FetchResult(status="unavailable", http_status=code)
    if code != 200:
        raise SourceError(f"house {house_id}: HTTP {code}")

    body = response.content
    _validate(body, house_id)
    return FetchResult(
        status="ok",
        http_status=code,
        body=body,
        last_modified=response.headers.get("Last-Modified"),
    )


def _validate(body: bytes, house_id: int) -> None:
    """Reject bodies that are not a commodities snapshot, so Bronze never stores junk."""
    try:
        parsed = json.loads(body)
    except ValueError as exc:
        raise SourceError(f"house {house_id}: unexpected response body (not JSON)") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("auctions"), list):
        raise SourceError(f"house {house_id}: unexpected response body (no auctions list)")

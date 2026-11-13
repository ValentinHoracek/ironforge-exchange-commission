"""Load the ingest configuration (API settings and markets) from a TOML file.

Endpoints and house IDs are configuration, not code: the Forever API is undocumented
and has already changed shape once (design doc 5.1.1).
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """The configuration file is invalid."""


@dataclass(frozen=True)
class ApiConfig:
    oauth_url: str
    base_url: str
    namespace: str
    ruleset_id: int


@dataclass(frozen=True)
class Market:
    house_id: int
    region: str
    ruleset: str
    faction: str
    mapping: str  # "verified" or "inferred" (how the house ID was mapped to the market)


@dataclass(frozen=True)
class Config:
    api: ApiConfig
    markets: tuple[Market, ...]


def load_config(path: Path) -> Config:
    with path.open("rb") as f:
        raw = tomllib.load(f)

    markets = tuple(Market(**m) for m in raw.get("markets", []))
    if not markets:
        raise ConfigError(f"{path}: no markets configured")

    seen: set[int] = set()
    for market in markets:
        if market.house_id in seen:
            raise ConfigError(f"{path}: duplicate house_id {market.house_id}")
        seen.add(market.house_id)

    return Config(api=ApiConfig(**raw["api"]), markets=markets)

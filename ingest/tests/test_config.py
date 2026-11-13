from pathlib import Path

import pytest

from ifec_ingest.config import ConfigError, load_config

VALID = """
[api]
oauth_url = "https://oauth.battle.net/token"
base_url = "https://eu.api.blizzard.com"
namespace = "dynamic-forever-eu"
ruleset_id = 2

[[markets]]
house_id = 111
region = "eu"
ruleset = "normal"
faction = "alliance"
mapping = "verified"

[[markets]]
house_id = 114
region = "eu"
ruleset = "normal"
faction = "horde"
mapping = "inferred"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ingest.toml"
    path.write_text(text)
    return path


def test_loads_api_settings_and_markets(tmp_path):
    config = load_config(write(tmp_path, VALID))

    assert config.api.namespace == "dynamic-forever-eu"
    assert config.api.ruleset_id == 2
    assert [m.house_id for m in config.markets] == [111, 114]
    assert config.markets[1].faction == "horde"
    assert config.markets[1].mapping == "inferred"


def test_rejects_duplicate_house_ids(tmp_path):
    text = VALID.replace("house_id = 114", "house_id = 111")

    with pytest.raises(ConfigError, match="duplicate house_id 111"):
        load_config(write(tmp_path, text))


def test_rejects_config_without_markets(tmp_path):
    text = VALID.split("[[markets]]")[0]

    with pytest.raises(ConfigError, match="no markets"):
        load_config(write(tmp_path, text))


def test_shipped_config_is_valid():
    shipped = Path(__file__).parents[1] / "config" / "ingest.toml"

    config = load_config(shipped)

    assert {m.house_id for m in config.markets} == {111, 114}

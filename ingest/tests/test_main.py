import json
from pathlib import Path

import httpx

from ifec_ingest.main import main

CONFIG = Path(__file__).parents[1] / "config" / "ingest.toml"
ENV = {"BLIZZARD_CLIENT_ID": "id", "BLIZZARD_CLIENT_SECRET": "secret"}
BODY = json.dumps({"auctions": [{"id": 1, "unit_price": 100}]}).encode()


def blizzard(house_status: int) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth.battle.net":
            return httpx.Response(200, json={"access_token": "tok"})
        headers = {"Last-Modified": "Fri, 13 Nov 2026 14:22:31 GMT"}
        return httpx.Response(house_status, content=BODY, headers=headers)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_local_run_stores_snapshots_and_exits_zero(tmp_path):
    code = main(["--local-dir", str(tmp_path), "--config", str(CONFIG)], ENV, blizzard(200))

    assert code == 0
    assert len(list((tmp_path / "bronze" / "commodities").rglob("*.json.gz"))) == 2
    assert (tmp_path / "serving" / "ops" / "ingest_status.json").exists()


def test_failed_run_exits_one(tmp_path):
    code = main(["--local-dir", str(tmp_path), "--config", str(CONFIG)], ENV, blizzard(500))

    assert code == 1


def test_missing_credentials_exit_two_without_calling_the_api(tmp_path, capsys):
    def no_calls(request):
        raise AssertionError("API must not be called")

    client = httpx.Client(transport=httpx.MockTransport(no_calls))

    code = main(["--local-dir", str(tmp_path), "--config", str(CONFIG)], {}, client)

    assert code == 2
    assert "BLIZZARD_CLIENT_ID" in capsys.readouterr().err


def test_secret_never_appears_in_output(tmp_path, capsys):
    env = {"BLIZZARD_CLIENT_ID": "id", "BLIZZARD_CLIENT_SECRET": "super-secret-value"}

    main(["--local-dir", str(tmp_path), "--config", str(CONFIG)], env, blizzard(200))

    out = capsys.readouterr()
    assert "super-secret-value" not in out.out + out.err


def test_storage_target_is_required(tmp_path, capsys):
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--config", str(CONFIG)], ENV, blizzard(200))

    assert exc.value.code == 2
    assert "--local-dir" in capsys.readouterr().err


def test_local_dir_and_storage_account_are_mutually_exclusive(tmp_path):
    import pytest

    argv = ["--local-dir", str(tmp_path), "--storage-account", "stx", "--config", str(CONFIG)]
    with pytest.raises(SystemExit) as exc:
        main(argv, ENV, blizzard(200))

    assert exc.value.code == 2


def test_storage_account_selects_azure_blob_storage(monkeypatch, tmp_path):
    from fakes import InMemoryStorage

    from ifec_ingest import main as main_module

    created = {}

    def fake_azure(account_url):
        created["url"] = account_url
        return InMemoryStorage()

    monkeypatch.setattr(main_module, "AzureBlobStorage", fake_azure)

    code = main(
        ["--storage-account", "stifecproda497a1", "--config", str(CONFIG)], ENV, blizzard(200)
    )

    assert code == 0
    assert created["url"] == "https://stifecproda497a1.blob.core.windows.net"

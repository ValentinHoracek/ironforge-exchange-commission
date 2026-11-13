import gzip
import hashlib
import json
from datetime import UTC, datetime

import httpx
from fakes import InMemoryStorage

from ifec_ingest.config import ApiConfig, Config, Market
from ifec_ingest.ingest import STATUS_PATH, run_ingest

API = ApiConfig(
    oauth_url="https://oauth.battle.net/token",
    base_url="https://eu.api.blizzard.com",
    namespace="dynamic-forever-eu",
    ruleset_id=2,
)
CONFIG = Config(
    api=API,
    markets=(
        Market(111, "eu", "normal", "alliance", "verified"),
        Market(114, "eu", "normal", "horde", "inferred"),
    ),
)
NOW = datetime(2026, 11, 13, 14, 30, 0, tzinfo=UTC)
LM_1 = "Fri, 13 Nov 2026 14:22:31 GMT"
LM_2 = "Fri, 13 Nov 2026 15:22:40 GMT"


def body(n: int) -> bytes:
    return json.dumps({"auctions": [{"id": i, "unit_price": 100} for i in range(n)]}).encode()


class FakeBlizzard:
    """A fake Blizzard API. `houses` maps house_id -> (status, body, last_modified)."""

    def __init__(self, houses: dict, token_status: int = 200) -> None:
        self.houses = houses
        self.token_status = token_status
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "oauth.battle.net":
            return httpx.Response(self.token_status, json={"access_token": "tok"})
        house_id = int(request.url.path.split("/")[-2])
        status, content, last_modified = self.houses[house_id]
        headers = {"Last-Modified": last_modified} if last_modified else {}
        return httpx.Response(status, content=content or b"", headers=headers)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def run(storage, blizzard, run_id="run-1"):
    return run_ingest(
        config=CONFIG,
        storage=storage,
        http=blizzard.client(),
        client_id="id",
        client_secret="secret",
        run_id=run_id,
        clock=lambda: NOW,
    )


def status_file(storage) -> dict:
    return json.loads(storage.read("serving", STATUS_PATH))


def test_new_snapshots_are_stored_raw_with_metadata():
    storage = InMemoryStorage()
    blizzard = FakeBlizzard({111: (200, body(3), LM_1), 114: (200, body(5), LM_1)})

    record = run(storage, blizzard)

    assert record["status"] == "success"
    assert [h["result"] for h in record["houses"]] == ["stored", "stored"]
    snapshots = [p for p in storage.paths("bronze") if p.endswith(".json.gz")]
    assert len(snapshots) == 2
    stored_111 = next(p for p in snapshots if "house=111" in p)
    assert gzip.decompress(storage.read("bronze", stored_111)) == body(3)
    meta = json.loads(storage.read("bronze", stored_111.replace(".json.gz", ".meta.json")))
    assert meta["sha256"] == hashlib.sha256(body(3)).hexdigest()
    assert meta["run_id"] == "run-1"


def test_status_file_tracks_each_house():
    storage = InMemoryStorage()
    run(storage, FakeBlizzard({111: (200, body(3), LM_1), 114: (200, body(5), LM_1)}))

    status = status_file(storage)

    assert status["last_run"]["status"] == "success"
    assert status["houses"]["111"]["last_modified"] == LM_1
    assert status["houses"]["111"]["sha256"] == hashlib.sha256(body(3)).hexdigest()
    assert status["houses"]["111"]["last_stored_at"] == "2026-11-13T14:30:00Z"


def test_second_run_sends_if_modified_since_and_handles_not_modified():
    storage = InMemoryStorage()
    run(storage, FakeBlizzard({111: (200, body(3), LM_1), 114: (200, body(5), LM_1)}))
    second = FakeBlizzard({111: (304, None, None), 114: (304, None, None)})

    record = run(storage, second, run_id="run-2")

    sent = [r.headers.get("if-modified-since") for r in second.requests if "auctions" in r.url.path]
    assert sent == [LM_1, LM_1]
    assert [h["result"] for h in record["houses"]] == ["not_modified", "not_modified"]
    assert len([p for p in storage.paths("bronze") if p.endswith(".json.gz")]) == 2


def test_identical_body_is_not_stored_twice():
    storage = InMemoryStorage()
    run(storage, FakeBlizzard({111: (200, body(3), LM_1), 114: (200, body(5), LM_1)}))

    record = run(
        storage,
        FakeBlizzard({111: (200, body(3), LM_2), 114: (200, body(5), LM_1)}),
        run_id="run-2",
    )

    assert [h["result"] for h in record["houses"]] == ["duplicate", "duplicate"]
    assert len([p for p in storage.paths("bronze") if p.endswith(".json.gz")]) == 2


def test_changed_body_with_same_last_modified_is_stored():
    """Seen on 2026-11-06: same Last-Modified, different body. The hash decides."""
    storage = InMemoryStorage()
    run(storage, FakeBlizzard({111: (200, body(3), LM_1), 114: (200, body(5), LM_1)}))

    record = run(
        storage, FakeBlizzard({111: (200, body(4), LM_1), 114: (304, None, None)}), run_id="run-2"
    )

    assert record["houses"][0]["result"] == "stored"
    assert len([p for p in storage.paths("bronze") if "house=111" in p and p.endswith(".gz")]) == 2


def test_one_failing_house_does_not_stop_the_others_but_fails_the_run():
    storage = InMemoryStorage()

    record = run(storage, FakeBlizzard({111: (503, None, None), 114: (200, body(5), LM_1)}))

    assert record["status"] == "failed"
    assert record["houses"][0]["result"] == "failed"
    assert "503" in record["houses"][0]["error"]
    assert record["houses"][1]["result"] == "stored"


def test_failed_house_keeps_its_previous_state():
    storage = InMemoryStorage()
    run(storage, FakeBlizzard({111: (200, body(3), LM_1), 114: (200, body(5), LM_1)}))

    run(storage, FakeBlizzard({111: (503, None, None), 114: (304, None, None)}), run_id="run-2")

    house = status_file(storage)["houses"]["111"]
    assert house["last_modified"] == LM_1
    assert house["last_result"] == "failed"


def test_unavailable_source_is_recorded_without_failing_the_run():
    storage = InMemoryStorage()

    record = run(storage, FakeBlizzard({111: (404, None, None), 114: (403, None, None)}))

    assert record["status"] == "success"
    assert [h["result"] for h in record["houses"]] == ["unavailable", "unavailable"]


def test_token_failure_fails_the_run_and_is_still_recorded():
    storage = InMemoryStorage()
    blizzard = FakeBlizzard({}, token_status=401)

    record = run(storage, blizzard)

    assert record["status"] == "failed"
    assert "401" in record["error"]
    assert status_file(storage)["last_run"]["status"] == "failed"
    assert storage.paths("bronze") == ["runs/date=2026-11-13/20261113T143000Z_run-1.json"]


def test_every_run_writes_an_immutable_run_record():
    storage = InMemoryStorage()

    run(storage, FakeBlizzard({111: (200, body(3), LM_1), 114: (304, None, None)}))

    path = "runs/date=2026-11-13/20261113T143000Z_run-1.json"
    saved = json.loads(storage.read("bronze", path))
    assert saved["run_id"] == "run-1"
    assert saved["started_at"] == "2026-11-13T14:30:00Z"
    assert len(saved["houses"]) == 2


def test_rerun_after_lost_status_does_not_overwrite_bronze():
    storage = InMemoryStorage()
    blizzard = FakeBlizzard({111: (200, body(3), LM_1), 114: (304, None, None)})
    run(storage, blizzard)
    storage.blobs.pop(("serving", STATUS_PATH))  # status file lost

    record = run(storage, blizzard, run_id="run-2")

    assert record["houses"][0]["result"] == "duplicate"


def test_crash_between_data_and_metadata_is_repaired_on_next_run():
    storage = InMemoryStorage()
    blizzard = FakeBlizzard({111: (200, body(3), LM_1), 114: (304, None, None)})
    run(storage, blizzard)
    meta = next(p for p in storage.paths("bronze") if p.endswith(".meta.json"))
    storage.blobs.pop(("bronze", meta))  # crash: data written, metadata not
    storage.blobs.pop(("serving", STATUS_PATH))

    run(storage, blizzard, run_id="run-2")

    assert json.loads(storage.read("bronze", meta))["run_id"] == "run-2"

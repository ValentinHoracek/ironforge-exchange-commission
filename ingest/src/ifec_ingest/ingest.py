"""One ingest run: capture new commodities snapshots for every configured market.

Results per house:
  stored        new snapshot written to Bronze
  not_modified  API answered 304 to If-Modified-Since
  duplicate     body identical to one already stored (SHA-256)
  unavailable   API answered 403/404 (namespace or house not served) - monitored, not a failure
  failed        any other error; the run fails, other houses still run
"""

import hashlib
import json
from collections.abc import Callable
from datetime import datetime

import httpx

from ifec_ingest.blizzard import SourceError, commodities_url, fetch_commodities, get_token
from ifec_ingest.bronze import compress, iso_utc, metadata_record, snapshot_paths, snapshot_time
from ifec_ingest.config import Config, Market
from ifec_ingest.storage import AlreadyExists, Storage

BRONZE = "bronze"
SERVING = "serving"
STATUS_PATH = "ops/ingest_status.json"


def run_ingest(
    *,
    config: Config,
    storage: Storage,
    http: httpx.Client,
    client_id: str,
    client_secret: str,
    run_id: str,
    clock: Callable[[], datetime],
) -> dict:
    started_at = clock()
    status = _load_status(storage)
    record: dict = {
        "job": "ingest",
        "run_id": run_id,
        "started_at": iso_utc(started_at),
        "status": "success",
        "error": None,
        "houses": [],
    }

    try:
        token = get_token(http, config.api, client_id, client_secret)
    except (SourceError, httpx.HTTPError) as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
    else:
        for market in config.markets:
            previous = status["houses"].get(str(market.house_id), {})
            result = _ingest_house(config, storage, http, token, market, previous, run_id, clock)
            record["houses"].append(result)
            status["houses"][str(market.house_id)] = _house_status(previous, result, clock())
        if any(h["result"] == "failed" for h in record["houses"]):
            record["status"] = "failed"

    record["finished_at"] = iso_utc(clock())
    status["last_run"] = {k: record[k] for k in ("run_id", "status", "started_at", "finished_at")}

    run_path = f"runs/date={started_at:%Y-%m-%d}/{started_at:%Y%m%dT%H%M%SZ}_{run_id}.json"
    storage.write(BRONZE, run_path, _to_json(record), overwrite=False)
    storage.write(SERVING, STATUS_PATH, _to_json(status), overwrite=True)
    return record


def _ingest_house(
    config: Config,
    storage: Storage,
    http: httpx.Client,
    token: str,
    market: Market,
    previous: dict,
    run_id: str,
    clock: Callable[[], datetime],
) -> dict:
    result: dict = {"house_id": market.house_id, "result": None, "error": None}
    try:
        fetched_at = clock()
        fetch = fetch_commodities(
            http, config.api, market.house_id, token, previous.get("last_modified")
        )
    except (SourceError, httpx.HTTPError) as exc:
        return result | {"result": "failed", "error": str(exc)}

    result["http_status"] = fetch.http_status
    if fetch.status != "ok":
        return result | {"result": fetch.status}

    sha256 = hashlib.sha256(fetch.body).hexdigest()
    result |= {"last_modified": fetch.last_modified, "sha256": sha256}
    if sha256 == previous.get("sha256"):
        return result | {"result": "duplicate"}

    snap_at = snapshot_time(fetch.last_modified, fetched_at)
    data_path, meta_path = snapshot_paths(market, snap_at, sha256)
    meta = metadata_record(
        market=market,
        body=fetch.body,
        sha256=sha256,
        last_modified=fetch.last_modified,
        http_status=fetch.http_status,
        fetched_at=fetched_at,
        namespace=config.api.namespace,
        source_url=commodities_url(config.api, market.house_id),
        run_id=run_id,
    )

    outcome = "stored"
    try:
        storage.write(BRONZE, data_path, compress(fetch.body), overwrite=False)
    except AlreadyExists:
        outcome = "duplicate"  # already captured by an earlier run
    try:
        storage.write(BRONZE, meta_path, _to_json(meta), overwrite=False)
    except AlreadyExists:
        pass
    return result | {"result": outcome, "path": data_path}


def _house_status(previous: dict, result: dict, now: datetime) -> dict:
    house = dict(previous)
    house["last_checked_at"] = iso_utc(now)
    house["last_result"] = result["result"]
    house["last_error"] = result["error"]
    if result["result"] in ("stored", "duplicate"):
        house["last_modified"] = result["last_modified"]
        house["sha256"] = result["sha256"]
    if result["result"] == "stored":
        house["last_stored_at"] = iso_utc(now)
        house["last_snapshot_path"] = result["path"]
    return house


def _load_status(storage: Storage) -> dict:
    raw = storage.read(SERVING, STATUS_PATH)
    status = json.loads(raw) if raw else {}
    status.setdefault("houses", {})
    return status


def _to_json(data: dict) -> bytes:
    return json.dumps(data, indent=2, sort_keys=True).encode()

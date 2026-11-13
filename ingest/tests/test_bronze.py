import gzip
import hashlib
from datetime import UTC, datetime

from ifec_ingest.bronze import (
    compress,
    metadata_record,
    snapshot_paths,
    snapshot_time,
)
from ifec_ingest.config import Market

MARKET = Market(house_id=111, region="eu", ruleset="normal", faction="alliance", mapping="verified")
FETCHED_AT = datetime(2026, 11, 13, 14, 30, 5, tzinfo=UTC)
BODY = b'{"auctions": []}'
SHA = hashlib.sha256(BODY).hexdigest()


def test_snapshot_time_comes_from_last_modified():
    assert snapshot_time("Fri, 13 Nov 2026 14:22:31 GMT", FETCHED_AT) == datetime(
        2026, 11, 13, 14, 22, 31, tzinfo=UTC
    )


def test_snapshot_time_falls_back_to_fetch_time_when_header_missing_or_bad():
    assert snapshot_time(None, FETCHED_AT) == FETCHED_AT
    assert snapshot_time("garbage", FETCHED_AT) == FETCHED_AT


def test_snapshot_paths_are_partitioned_by_market_and_snapshot_hour():
    snap = datetime(2026, 11, 13, 14, 22, 31, tzinfo=UTC)

    data_path, meta_path = snapshot_paths(MARKET, snap, SHA)

    prefix = "commodities/region=eu/ruleset=normal/house=111/date=2026-11-13/hour=14/"
    assert data_path == f"{prefix}20261113T142231Z_{SHA[:16]}.json.gz"
    assert meta_path == f"{prefix}20261113T142231Z_{SHA[:16]}.meta.json"


def test_compress_is_lossless_and_deterministic():
    assert gzip.decompress(compress(BODY)) == BODY
    assert compress(BODY) == compress(BODY)


def test_metadata_record_holds_integrity_and_lineage_fields():
    record = metadata_record(
        market=MARKET,
        body=BODY,
        sha256=SHA,
        last_modified="Fri, 13 Nov 2026 14:22:31 GMT",
        http_status=200,
        fetched_at=FETCHED_AT,
        namespace="dynamic-forever-eu",
        source_url="https://eu.api.blizzard.com/x",
        run_id="run-1",
    )

    assert record["sha256"] == SHA
    assert record["raw_bytes"] == len(BODY)
    assert record["house_id"] == 111
    assert record["faction"] == "alliance"
    assert record["house_mapping"] == "verified"
    assert record["last_modified"] == "Fri, 13 Nov 2026 14:22:31 GMT"
    assert record["fetched_at"] == "2026-11-13T14:30:05Z"
    assert record["run_id"] == "run-1"

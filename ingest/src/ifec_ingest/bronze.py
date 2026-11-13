"""Bronze layout: where raw snapshots are stored and what is recorded about them.

Bronze holds responses exactly as received (gzipped) and is never changed. Every
snapshot gets a metadata record next to it with the SHA-256 of the raw body as
integrity evidence.
"""

import gzip
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from ifec_ingest.config import Market


def snapshot_time(last_modified: str | None, fetched_at: datetime) -> datetime:
    """Snapshot time = the API's Last-Modified (when Blizzard built it), else fetch time."""
    if last_modified:
        try:
            return parsedate_to_datetime(last_modified).astimezone(UTC)
        except (TypeError, ValueError):
            pass
    return fetched_at


def snapshot_paths(market: Market, snapshot_at: datetime, sha256: str) -> tuple[str, str]:
    """Return (data path, metadata path) inside the bronze container.

    The hash prefix in the name keeps two different bodies with the same
    Last-Modified apart (seen on 2026-11-06).
    """
    prefix = (
        f"commodities/region={market.region}/ruleset={market.ruleset}/house={market.house_id}"
        f"/date={snapshot_at:%Y-%m-%d}/hour={snapshot_at:%H}/"
    )
    name = f"{snapshot_at:%Y%m%dT%H%M%SZ}_{sha256[:16]}"
    return f"{prefix}{name}.json.gz", f"{prefix}{name}.meta.json"


def compress(body: bytes) -> bytes:
    """Gzip with a fixed timestamp, so the same body always gives the same bytes."""
    return gzip.compress(body, mtime=0)


def metadata_record(
    *,
    market: Market,
    body: bytes,
    sha256: str,
    last_modified: str | None,
    http_status: int,
    fetched_at: datetime,
    namespace: str,
    source_url: str,
    run_id: str,
) -> dict:
    return {
        "house_id": market.house_id,
        "region": market.region,
        "ruleset": market.ruleset,
        "faction": market.faction,
        "house_mapping": market.mapping,
        "namespace": namespace,
        "source_url": source_url,
        "http_status": http_status,
        "last_modified": last_modified,
        "fetched_at": iso_utc(fetched_at),
        "raw_bytes": len(body),
        "sha256": sha256,
        "run_id": run_id,
    }


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

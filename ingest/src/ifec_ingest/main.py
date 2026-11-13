"""Command-line entry point for one ingest run.

Credentials come only from environment variables (in Azure: injected from Key Vault),
never from arguments or files, so they cannot end up in shell history or git.

Exit codes: 0 = run succeeded, 1 = run failed (triggers the alert in Azure),
2 = misconfiguration (nothing was called).
"""

import argparse
import json
import os
import sys
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ifec_ingest.azure_storage import AzureBlobStorage
from ifec_ingest.config import load_config
from ifec_ingest.ingest import run_ingest
from ifec_ingest.local_storage import LocalFolderStorage
from ifec_ingest.storage import Storage

REQUIRED_ENV = ("BLIZZARD_CLIENT_ID", "BLIZZARD_CLIENT_SECRET")


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    http: httpx.Client | None = None,
) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(prog="ifec-ingest", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/ingest.toml"))
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--local-dir", type=Path, help="write to this folder (laptop test runs)")
    target.add_argument("--storage-account", help="write to this Azure storage account (data lake)")
    args = parser.parse_args(argv)

    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        print(f"missing environment variables: {', '.join(missing)}", file=sys.stderr)
        return 2

    # Container Apps sets the execution name; it makes the run ID traceable in Azure logs.
    run_id = env.get("CONTAINER_APP_JOB_EXECUTION_NAME") or f"local-{uuid.uuid4().hex[:8]}"

    record = run_ingest(
        config=load_config(args.config),
        storage=_storage(args),
        http=http or httpx.Client(timeout=60),
        client_id=env["BLIZZARD_CLIENT_ID"],
        client_secret=env["BLIZZARD_CLIENT_SECRET"],
        run_id=run_id,
        clock=lambda: datetime.now(UTC),
    )

    for house in record["houses"]:
        print(json.dumps({"run_id": run_id, **house}))
    print(json.dumps({k: v for k, v in record.items() if k != "houses"}))
    return 0 if record["status"] == "success" else 1


def _storage(args: argparse.Namespace) -> Storage:
    if args.storage_account:
        return AzureBlobStorage(f"https://{args.storage_account}.blob.core.windows.net")
    return LocalFolderStorage(args.local_dir)

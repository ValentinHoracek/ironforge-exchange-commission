"""Storage interface. The ingest logic depends only on this, not on Azure.

Implementations: AzureBlobStorage (azure_storage.py), LocalFolderStorage (local_storage.py)
and, in tests, InMemoryStorage (tests/fakes.py).
"""

from typing import Protocol


class AlreadyExists(Exception):  # noqa: N818 - reads naturally at call sites
    """A blob that must not be overwritten already exists."""


class Storage(Protocol):
    def read(self, container: str, path: str) -> bytes | None: ...

    def write(self, container: str, path: str, data: bytes, *, overwrite: bool) -> None: ...

"""Test doubles. Kept out of the production package."""

from ifec_ingest.storage import AlreadyExists


class InMemoryStorage:
    """Behaves like the blob storage used in production: containers of path -> bytes."""

    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], bytes] = {}

    def read(self, container: str, path: str) -> bytes | None:
        return self.blobs.get((container, path))

    def write(self, container: str, path: str, data: bytes, *, overwrite: bool) -> None:
        if not overwrite and (container, path) in self.blobs:
            raise AlreadyExists(f"{container}/{path}")
        self.blobs[(container, path)] = data

    def paths(self, container: str) -> list[str]:
        return sorted(p for c, p in self.blobs if c == container)

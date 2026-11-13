"""Storage in a local folder, for test runs on a laptop. Same rules as the cloud storage:
files written without `overwrite` are never replaced."""

from pathlib import Path

from ifec_ingest.storage import AlreadyExists


class LocalFolderStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()

    def read(self, container: str, path: str) -> bytes | None:
        target = self._target(container, path)
        return target.read_bytes() if target.exists() else None

    def write(self, container: str, path: str, data: bytes, *, overwrite: bool) -> None:
        target = self._target(container, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("wb" if overwrite else "xb") as f:
                f.write(data)
        except FileExistsError as exc:
            raise AlreadyExists(f"{container}/{path}") from exc

    def _target(self, container: str, path: str) -> Path:
        container_root = (self._root / container).resolve()
        target = (container_root / path).resolve()
        if not container_root.is_relative_to(self._root) or not target.is_relative_to(
            container_root
        ):
            raise ValueError(f"path {container}/{path} is outside the storage folder")
        return target

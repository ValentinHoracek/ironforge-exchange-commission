import pytest

from ifec_ingest.local_storage import LocalFolderStorage
from ifec_ingest.storage import AlreadyExists


def test_read_missing_file_returns_none(tmp_path):
    assert LocalFolderStorage(tmp_path).read("bronze", "a/b.json") is None


def test_write_creates_folders_and_read_returns_bytes(tmp_path):
    storage = LocalFolderStorage(tmp_path)

    storage.write("bronze", "a/b/c.json", b"data", overwrite=False)

    assert (tmp_path / "bronze" / "a" / "b" / "c.json").read_bytes() == b"data"
    assert storage.read("bronze", "a/b/c.json") == b"data"


def test_write_without_overwrite_refuses_existing_file(tmp_path):
    storage = LocalFolderStorage(tmp_path)
    storage.write("bronze", "x.json", b"first", overwrite=False)

    with pytest.raises(AlreadyExists):
        storage.write("bronze", "x.json", b"second", overwrite=False)
    assert storage.read("bronze", "x.json") == b"first"


def test_write_with_overwrite_replaces_file(tmp_path):
    storage = LocalFolderStorage(tmp_path)
    storage.write("serving", "s.json", b"old", overwrite=True)

    storage.write("serving", "s.json", b"new", overwrite=True)

    assert storage.read("serving", "s.json") == b"new"


@pytest.mark.parametrize("path", ["../escape.json", "a/../../escape.json", "/etc/passwd"])
def test_paths_cannot_escape_the_root_folder(tmp_path, path):
    storage = LocalFolderStorage(tmp_path / "root")

    with pytest.raises(ValueError, match="outside"):
        storage.write("bronze", path, b"x", overwrite=True)

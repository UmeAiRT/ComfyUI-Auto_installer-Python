"""Extended tests for the download utility module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from src.utils.download import (
    _find_aria2c,
    download_file,
    verify_checksum,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestFindAria2c:
    """Tests for _find_aria2c."""

    def test_finds_on_system_path(self) -> None:
        from pathlib import Path as _Path

        with patch("src.utils.download.shutil.which", return_value="/usr/bin/aria2c"):
            result = _find_aria2c()
            assert result is not None
            assert result == _Path("/usr/bin/aria2c")

    def test_none_when_not_found(self) -> None:
        with patch("src.utils.download.shutil.which", return_value=None):
            result = _find_aria2c()
            # Falls through to hint + package-relative, both missing
            assert result is None

    def test_finds_in_hint_dir(self, tmp_path: Path) -> None:
        import sys

        exe_name = "aria2c.exe" if sys.platform == "win32" else "aria2c"
        exe = tmp_path / exe_name
        exe.touch()

        with patch("src.utils.download.shutil.which", return_value=None):
            result = _find_aria2c(aria2c_hint=tmp_path)
            assert result is not None
            assert result == exe


class TestVerifyChecksum:
    """Tests for verify_checksum."""

    def test_correct_checksum(self, tmp_path: Path) -> None:
        import hashlib

        content = b"test file content"
        path = tmp_path / "testfile.bin"
        path.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert verify_checksum(path, expected) is True

    def test_wrong_checksum(self, tmp_path: Path) -> None:
        path = tmp_path / "testfile.bin"
        path.write_bytes(b"some content")
        assert verify_checksum(path, "0" * 64) is False


class TestDownloadFile:
    """Tests for download_file (mocked I/O)."""

    def test_skip_existing_file(self, tmp_path: Path) -> None:
        """Should skip download if file already exists and force=False."""
        dest = tmp_path / "existing.bin"
        dest.write_bytes(b"already here")

        log = MagicMock()
        result = download_file(
            "https://example.com/existing.bin",
            dest,
            log=log,
        )
        assert result == dest
        # Check the log message includes the filename
        sub_calls = [str(c) for c in log.sub.call_args_list]
        assert any("already exists" in c for c in sub_calls)

    def test_force_redownload(self, tmp_path: Path) -> None:
        """Should re-download if force=True even if file exists."""
        dest = tmp_path / "existing.bin"
        dest.write_bytes(b"old content")

        log = MagicMock()
        with (
            patch("src.utils.download._find_aria2c", return_value=None),
            patch("src.utils.download._download_with_httpx") as mock_httpx,
        ):
            download_file(
                "https://example.com/existing.bin",
                dest,
                force=True,
                log=log,
            )
            mock_httpx.assert_called_once()

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        """Should create parent directories if they don't exist."""
        dest = tmp_path / "subdir" / "deep" / "file.bin"

        log = MagicMock()
        with (
            patch("src.utils.download._find_aria2c", return_value=None),
            patch("src.utils.download._download_with_httpx") as mock_httpx,
        ):
            download_file(
                "https://example.com/file.bin",
                dest,
                log=log,
            )
            mock_httpx.assert_called_once()
            assert dest.parent.exists()

    def test_tries_multiple_urls(self, tmp_path: Path) -> None:
        """Should try fallback URLs when primary fails."""
        dest = tmp_path / "file.bin"

        call_count = 0

        def side_effect(url, dest_path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("first URL failed")  # OSError is caught by download_file
            # Second URL succeeds (no exception = success)

        log = MagicMock()
        with (
            patch("src.utils.download._find_aria2c", return_value=None),
            patch("src.utils.download._download_with_httpx", side_effect=side_effect),
        ):
            download_file(
                ["https://primary.com/file.bin", "https://fallback.com/file.bin"],
                dest,
                log=log,
            )
            assert call_count == 2

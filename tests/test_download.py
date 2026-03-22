"""Tests for the download utility."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from src.utils.download import verify_checksum

if TYPE_CHECKING:
    from pathlib import Path


class TestVerifyChecksum:
    """Tests for SHA256 checksum verification."""

    def test_valid_checksum(self, tmp_path: Path) -> None:
        """Checksum matches file content."""
        test_file = tmp_path / "test.bin"
        content = b"hello world"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest()
        assert verify_checksum(test_file, expected) is True

    def test_invalid_checksum(self, tmp_path: Path) -> None:
        """Checksum mismatch is detected."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world")

        assert verify_checksum(test_file, "0" * 64) is False

    def test_case_insensitive(self, tmp_path: Path) -> None:
        """Checksum comparison is case-insensitive."""
        test_file = tmp_path / "test.bin"
        content = b"test data"
        test_file.write_bytes(content)

        expected = hashlib.sha256(content).hexdigest().upper()
        assert verify_checksum(test_file, expected) is True

    def test_empty_file(self, tmp_path: Path) -> None:
        """Checksum of empty file works correctly."""
        test_file = tmp_path / "empty.bin"
        test_file.write_bytes(b"")

        expected = hashlib.sha256(b"").hexdigest()
        assert verify_checksum(test_file, expected) is True

class TestDownloadFileFallback:
    """Tests for auto fallback behaviors in download_file."""

    def test_auto_modelscope_fallback(self, tmp_path: Path) -> None:
        """UmeAiRT HF URLs automatically get MS fallback injected."""
        from unittest.mock import MagicMock, patch

        from src.utils.download import download_file

        dest = tmp_path / "test.whl"
        hf_url = "https://huggingface.co/UmeAiRT/ComfyUI-Auto_installer/resolve/main/whl/nunchaku.whl"
        expected_ms = "https://www.modelscope.ai/datasets/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/master/whl/nunchaku.whl"

        mirrors = {
            "https://huggingface.co/UmeAiRT/ComfyUI-Auto_installer/resolve/main/": "https://www.modelscope.ai/datasets/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/master/"
        }

        mock_httpx = MagicMock()
        # Always fail to trigger all fallbacks
        mock_httpx.side_effect = OSError("Download failed")

        import contextlib
        with patch("src.utils.download._find_aria2c", return_value=None), \
             patch("src.utils.download._download_with_httpx", mock_httpx), \
             contextlib.suppress(RuntimeError):
            download_file(hf_url, dest, mirrors=mirrors)

        # httpx should have been called twice: once with HF, once with MS
        assert mock_httpx.call_count == 2
        calls = mock_httpx.call_args_list
        assert calls[0][0][0] == hf_url
        assert calls[1][0][0] == expected_ms

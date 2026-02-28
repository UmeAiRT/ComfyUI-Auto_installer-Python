"""Tests for the download utility."""

from __future__ import annotations

import hashlib
from pathlib import Path

from src.utils.download import verify_checksum


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

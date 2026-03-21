"""Tests for the Python version detection utility."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.python_info import detect_venv_python_version


class TestDetectVenvPythonVersion:
    """Tests for detect_venv_python_version."""

    def test_parses_valid_output(self, tmp_path: Path) -> None:
        """Should parse '3 13' into (3, 13)."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="3 13\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            assert detect_venv_python_version(tmp_path / "python") == (3, 13)

    def test_parses_311(self, tmp_path: Path) -> None:
        """Should parse '3 11' into (3, 11)."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="3 11\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            assert detect_venv_python_version(tmp_path / "python") == (3, 11)

    def test_raises_on_nonzero_exit(self, tmp_path: Path) -> None:
        """Should raise RuntimeError if subprocess exits non-zero."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="exit 1"):
                detect_venv_python_version(tmp_path / "python")

    def test_raises_on_unexpected_output(self, tmp_path: Path) -> None:
        """Should raise RuntimeError if output format is unexpected."""
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="Python 3.13\n", stderr=""
        )
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="parse"):
                detect_venv_python_version(tmp_path / "python")

    def test_raises_on_timeout(self, tmp_path: Path) -> None:
        """Should raise RuntimeError if subprocess times out."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="python", timeout=10),
        ):
            with pytest.raises(RuntimeError, match="Failed"):
                detect_venv_python_version(tmp_path / "python")

    def test_raises_on_file_not_found(self, tmp_path: Path) -> None:
        """Should raise RuntimeError if python executable doesn't exist."""
        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("No such file"),
        ):
            with pytest.raises(RuntimeError, match="Failed"):
                detect_venv_python_version(tmp_path / "python")

"""Tests for the GPU detection and selection module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from src.enums import InstallerFatalError
from src.installer.gpu_setup import detect_and_select_gpu

if TYPE_CHECKING:
    pass


def _make_deps(supported_tags: list[str] | None = None) -> MagicMock:
    """Create a mock DependenciesConfig with supported_cuda_tags."""
    deps = MagicMock()
    deps.pip_packages.supported_cuda_tags = supported_tags or ["cu130", "cu128"]
    return deps


def _make_platform(name: str) -> MagicMock:
    """Create a mock Platform with a given name."""
    platform = MagicMock()
    platform.name = name
    return platform


class TestManualOverride:
    """Tests for the manual cuda_override path."""

    def test_returns_override_as_is(self) -> None:
        """When cuda_override is provided, return it directly."""
        log = MagicMock()
        result = detect_and_select_gpu(
            _make_platform("windows"), _make_deps(), log, cuda_override="cu128"
        )
        assert result == "cu128"
        log.sub.assert_called_once()

    def test_override_skips_detection(self) -> None:
        """Manual override should not call any detection functions."""
        log = MagicMock()
        with patch("src.installer.gpu_setup.detect_cuda_version") as mock_cuda:
            detect_and_select_gpu(
                _make_platform("windows"), _make_deps(), log, cuda_override="cu130"
            )
            mock_cuda.assert_not_called()


class TestMacOS:
    """Tests for the macOS MPS path."""

    def test_macos_returns_none(self) -> None:
        """macOS should return None (MPS backend, no cuda tag)."""
        log = MagicMock()
        result = detect_and_select_gpu(_make_platform("macos"), _make_deps(), log)
        assert result is None


class TestNvidiaDetection:
    """Tests for NVIDIA GPU detection."""

    def test_nvidia_supported_cuda(self) -> None:
        """Should return the detected cuda_tag when in supported list."""
        log = MagicMock()
        with (
            patch("src.installer.gpu_setup.detect_cuda_version", return_value=(13, 0)),
            patch("src.installer.gpu_setup.cuda_tag_from_version", return_value="cu130"),
            patch("src.installer.gpu_setup.check_amd_gpu"),
        ):
            result = detect_and_select_gpu(_make_platform("windows"), _make_deps(), log)
        assert result == "cu130"

    def test_nvidia_unsupported_falls_back_to_cu130(self) -> None:
        """Should fall back to cu130 when detected CUDA is not in supported list."""
        log = MagicMock()
        deps = _make_deps(["cu130", "cu128"])
        with (
            patch("src.installer.gpu_setup.detect_cuda_version", return_value=(11, 7)),
            patch("src.installer.gpu_setup.cuda_tag_from_version", return_value="cu117"),
            patch("src.installer.gpu_setup.check_amd_gpu"),
        ):
            result = detect_and_select_gpu(_make_platform("windows"), deps, log)
        assert result == "cu130"
        log.warning.assert_called_once()


class TestAmdDetection:
    """Tests for AMD GPU detection."""

    def test_amd_linux_returns_rocm(self) -> None:
        """AMD on Linux should return rocm71."""
        log = MagicMock()
        with (
            patch("src.installer.gpu_setup.detect_cuda_version", return_value=None),
            patch("src.installer.gpu_setup.cuda_tag_from_version", return_value=None),
            patch("src.installer.gpu_setup.check_amd_gpu", return_value=True),
        ):
            result = detect_and_select_gpu(_make_platform("linux"), _make_deps(), log)
        assert result == "rocm71"

    def test_amd_windows_returns_directml(self) -> None:
        """AMD on Windows should return directml."""
        log = MagicMock()
        with (
            patch("src.installer.gpu_setup.detect_cuda_version", return_value=None),
            patch("src.installer.gpu_setup.cuda_tag_from_version", return_value=None),
            patch("src.installer.gpu_setup.check_amd_gpu", return_value=True),
        ):
            result = detect_and_select_gpu(_make_platform("windows"), _make_deps(), log)
        assert result == "directml"


class TestNoGpu:
    """Tests for the no-GPU fallback path."""

    def test_no_gpu_user_accepts_cpu(self) -> None:
        """When no GPU and user confirms, should return 'cpu'."""
        log = MagicMock()
        with (
            patch("src.installer.gpu_setup.detect_cuda_version", return_value=None),
            patch("src.installer.gpu_setup.cuda_tag_from_version", return_value=None),
            patch("src.installer.gpu_setup.check_amd_gpu", return_value=False),
            patch("src.installer.gpu_setup.confirm", return_value=True),
        ):
            result = detect_and_select_gpu(_make_platform("windows"), _make_deps(), log)
        assert result == "cpu"

    def test_no_gpu_user_declines_raises(self) -> None:
        """When no GPU and user declines, should raise InstallerFatalError."""
        log = MagicMock()
        with (
            patch("src.installer.gpu_setup.detect_cuda_version", return_value=None),
            patch("src.installer.gpu_setup.cuda_tag_from_version", return_value=None),
            patch("src.installer.gpu_setup.check_amd_gpu", return_value=False),
            patch("src.installer.gpu_setup.confirm", return_value=False),
            pytest.raises(InstallerFatalError, match="No physical GPU"),
        ):
            detect_and_select_gpu(_make_platform("windows"), _make_deps(), log)

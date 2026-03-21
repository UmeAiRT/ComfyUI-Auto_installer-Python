"""Extended tests for GPU detection and VRAM info utilities."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from src.utils.gpu import (
    GpuInfo,
    cuda_tag_from_version,
    detect_cuda_version,
    detect_nvidia_gpu,
    display_gpu_recommendations,
    get_gpu_vram_info,
    recommend_model_quality,
)


class TestDetectCudaVersion:
    """Tests for detect_cuda_version."""

    def test_cuda_13_0(self) -> None:
        mock_r = MagicMock(returncode=0, stdout="570.10\n")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert detect_cuda_version() == (13, 0)

    def test_cuda_12_8(self) -> None:
        mock_r = MagicMock(returncode=0, stdout="560.20\n")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert detect_cuda_version() == (12, 8)

    def test_no_nvidia_smi(self) -> None:
        with patch("src.utils.gpu.subprocess.run", side_effect=FileNotFoundError):
            assert detect_cuda_version() is None

    def test_failed_returncode(self) -> None:
        mock_r = MagicMock(returncode=1, stdout="")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert detect_cuda_version() is None

    def test_old_driver(self) -> None:
        """Really old driver should return None."""
        mock_r = MagicMock(returncode=0, stdout="400.00\n")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert detect_cuda_version() is None


class TestDetectNvidiaGpu:
    """Tests for detect_nvidia_gpu."""

    def test_detected(self) -> None:
        mock_r = MagicMock(returncode=0, stdout="GPU 0: NVIDIA RTX 4090\n")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert detect_nvidia_gpu() is True

    def test_not_detected(self) -> None:
        mock_r = MagicMock(returncode=0, stdout="No devices found\n")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert detect_nvidia_gpu() is False

    def test_nvidia_smi_missing(self) -> None:
        with patch("src.utils.gpu.subprocess.run", side_effect=FileNotFoundError):
            assert detect_nvidia_gpu() is False

    def test_timeout(self) -> None:
        with patch(
            "src.utils.gpu.subprocess.run",
            side_effect=subprocess.TimeoutExpired("nvidia-smi", 10),
        ):
            assert detect_nvidia_gpu() is False


class TestGetGpuVramInfo:
    """Tests for get_gpu_vram_info."""

    def test_returns_info(self) -> None:
        mock_r = MagicMock(returncode=0, stdout="NVIDIA RTX 4090, 24564\n")
        with (
            patch("src.utils.gpu.subprocess.run", return_value=mock_r),
            patch("src.utils.gpu.detect_cuda_version", return_value=(13, 0)),
        ):
            gpu = get_gpu_vram_info()
            assert gpu is not None
            assert gpu.name == "NVIDIA RTX 4090"
            assert gpu.vram_gib == 24
            assert gpu.cuda_version == (13, 0)

    def test_returns_none_on_failure(self) -> None:
        mock_r = MagicMock(returncode=1, stdout="")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert get_gpu_vram_info() is None

    def test_returns_none_on_bad_output(self) -> None:
        mock_r = MagicMock(returncode=0, stdout="malformed\n")
        with patch("src.utils.gpu.subprocess.run", return_value=mock_r):
            assert get_gpu_vram_info() is None


class TestRecommendModelQuality:
    """Tests for recommend_model_quality."""

    def test_high_vram(self) -> None:
        assert recommend_model_quality(30) == "fp16"

    def test_24gb(self) -> None:
        assert recommend_model_quality(24) == "fp8 or GGUF Q8"

    def test_16gb(self) -> None:
        assert recommend_model_quality(16) == "GGUF Q6"

    def test_14gb(self) -> None:
        assert recommend_model_quality(14) == "GGUF Q5"

    def test_12gb(self) -> None:
        assert recommend_model_quality(12) == "GGUF Q4"

    def test_8gb(self) -> None:
        assert recommend_model_quality(8) == "GGUF Q3"

    def test_low_vram(self) -> None:
        assert recommend_model_quality(4) == "GGUF Q2"


class TestCudaTagFromVersion:
    """Tests for cuda_tag_from_version."""

    def test_cuda_13(self) -> None:
        assert cuda_tag_from_version((13, 0)) == "cu130"

    def test_cuda_12_8(self) -> None:
        assert cuda_tag_from_version((12, 8)) == "cu128"

    def test_old_cuda(self) -> None:
        assert cuda_tag_from_version((12, 1)) is None

    def test_none(self) -> None:
        assert cuda_tag_from_version(None) is None


class TestDisplayGpuRecommendations:
    """Tests for display_gpu_recommendations."""

    def test_with_nvidia_gpu(self) -> None:
        gpu = GpuInfo(name="RTX 4090", vram_gib=24, cuda_version=(13, 0))
        log = MagicMock()
        with patch("src.utils.gpu.get_gpu_vram_info", return_value=gpu):
            result = display_gpu_recommendations(log)
            assert result is not None
            assert result.name == "RTX 4090"

    def test_no_gpu(self) -> None:
        log = MagicMock()
        with (
            patch("src.utils.gpu.get_gpu_vram_info", return_value=None),
            patch("src.utils.gpu.check_amd_gpu", return_value=False),
        ):
            result = display_gpu_recommendations(log)
            assert result is None

    def test_amd_gpu_fallback(self) -> None:
        log = MagicMock()
        with (
            patch("src.utils.gpu.get_gpu_vram_info", return_value=None),
            patch("src.utils.gpu.check_amd_gpu", return_value=True),
        ):
            result = display_gpu_recommendations(log)
            assert result is None
            log.item.assert_any_call("AMD GPU detected.", style="success")

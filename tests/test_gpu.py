"""Tests for the GPU detection module."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from src.utils.gpu import GpuInfo, get_gpu_vram_info, recommend_model_quality


class TestRecommendModelQuality:
    """Tests for the VRAM-based recommendation logic."""

    def test_high_vram(self) -> None:
        assert recommend_model_quality(48) == "fp16"
        assert recommend_model_quality(30) == "fp16"

    def test_medium_vram(self) -> None:
        assert recommend_model_quality(24) == "fp8 or GGUF Q8"
        assert recommend_model_quality(18) == "fp8 or GGUF Q8"

    def test_16gb(self) -> None:
        assert recommend_model_quality(16) == "GGUF Q6"

    def test_14gb(self) -> None:
        assert recommend_model_quality(14) == "GGUF Q5"

    def test_12gb(self) -> None:
        assert recommend_model_quality(12) == "GGUF Q4"

    def test_8gb(self) -> None:
        assert recommend_model_quality(8) == "GGUF Q3"

    def test_low_vram(self) -> None:
        assert recommend_model_quality(6) == "GGUF Q2"
        assert recommend_model_quality(4) == "GGUF Q2"


class TestGetGpuVramInfo:
    """Tests for GPU detection with mocked nvidia-smi."""

    @patch("subprocess.run")
    def test_gpu_detected(self, mock_run) -> None:
        """Successfully detect GPU info."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="NVIDIA GeForce RTX 4090, 24564\n", stderr=""
        )

        info = get_gpu_vram_info()
        assert info is not None
        assert info.name == "NVIDIA GeForce RTX 4090"
        assert info.vram_gib == 24  # 24564 MiB ≈ 24 GiB

    @patch("subprocess.run")
    def test_no_gpu(self, mock_run) -> None:
        """Handle missing GPU gracefully."""
        mock_run.side_effect = FileNotFoundError("nvidia-smi not found")

        info = get_gpu_vram_info()
        assert info is None

    @patch("subprocess.run")
    def test_nvidia_smi_failure(self, mock_run) -> None:
        """Handle nvidia-smi returning non-zero."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="error"
        )

        info = get_gpu_vram_info()
        assert info is None

    @patch("subprocess.run")
    def test_unexpected_output(self, mock_run) -> None:
        """Handle unexpected nvidia-smi output format."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="garbage output", stderr=""
        )

        info = get_gpu_vram_info()
        assert info is None


class TestGpuInfo:
    """Tests for the GpuInfo dataclass."""

    def test_creation(self) -> None:
        info = GpuInfo(name="RTX 4090", vram_gib=24)
        assert info.name == "RTX 4090"
        assert info.vram_gib == 24

    def test_frozen(self) -> None:
        """GpuInfo should be immutable."""
        info = GpuInfo(name="RTX 4090", vram_gib=24)
        try:
            info.name = "RTX 3090"  # type: ignore
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass

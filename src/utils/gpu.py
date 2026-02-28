"""
GPU detection and VRAM information.

Replaces Test-NvidiaGpu and Get-GpuVramInfo from UmeAiRTUtils.psm1.
Uses subprocess to call nvidia-smi (works on both Windows and Linux).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from src.utils.logging import get_logger


@dataclass(frozen=True)
class GpuInfo:
    """Information about a detected NVIDIA GPU."""

    name: str
    vram_gib: int


def detect_nvidia_gpu() -> bool:
    """
    Check for the presence of an NVIDIA GPU.

    Returns:
        True if an NVIDIA GPU is detected, False otherwise.
    """
    log = get_logger()
    log.item("Checking for NVIDIA GPU...")

    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and "GPU 0:" in result.stdout:
            log.sub("NVIDIA GPU detected.", style="success")
            log.info(result.stdout.strip().split("\n")[0])
            return True
        else:
            log.warning("No NVIDIA GPU detected. Skipping GPU-only packages.", level=1)
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        log.warning("'nvidia-smi' command failed. Assuming no GPU.", level=1)
        return False


def get_gpu_vram_info() -> GpuInfo | None:
    """
    Query NVIDIA GPU name and total VRAM.

    Returns:
        GpuInfo object with name and VRAM in GiB, or None if detection fails.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        parts = result.stdout.strip().split(",")
        if len(parts) < 2:
            return None

        name = parts[0].strip()
        memory_mib = int(parts[1].strip())
        memory_gib = round(memory_mib / 1024)

        return GpuInfo(name=name, vram_gib=memory_gib)

    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        return None


def recommend_model_quality(vram_gib: int) -> str:
    """
    Recommend a model quality tier based on available VRAM.

    Args:
        vram_gib: Available VRAM in GiB.

    Returns:
        A recommendation string (e.g. "fp16", "GGUF Q4").
    """
    if vram_gib >= 30:
        return "fp16"
    elif vram_gib >= 18:
        return "fp8 or GGUF Q8"
    elif vram_gib >= 16:
        return "GGUF Q6"
    elif vram_gib >= 14:
        return "GGUF Q5"
    elif vram_gib >= 12:
        return "GGUF Q4"
    elif vram_gib >= 8:
        return "GGUF Q3"
    else:
        return "GGUF Q2"


def display_gpu_recommendations() -> GpuInfo | None:
    """
    Detect GPU and display VRAM-based model recommendations.

    Returns:
        The detected GpuInfo or None.
    """
    log = get_logger()

    log.log("─" * 70, level=-2)
    log.item("Checking for NVIDIA GPU to provide model recommendations...", style="warning")

    gpu = get_gpu_vram_info()
    if gpu:
        log.item(f"GPU: {gpu.name}", style="success")
        log.item(f"VRAM: {gpu.vram_gib} GB", style="success")
        rec = recommend_model_quality(gpu.vram_gib)
        log.item(f"Recommendation: {rec}", style="cyan")
    else:
        log.item("No NVIDIA GPU detected. Please choose based on your hardware.", style="info")

    log.log("─" * 70, level=-2)
    return gpu

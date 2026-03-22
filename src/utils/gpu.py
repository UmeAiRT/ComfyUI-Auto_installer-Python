"""
GPU detection, VRAM information, and CUDA version detection.

Replaces Test-NvidiaGpu and Get-GpuVramInfo from UmeAiRTUtils.psm1.
Uses subprocess to call nvidia-smi (works on both Windows and Linux).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.utils.logging import InstallerLogger

# NVIDIA driver version → minimum CUDA toolkit version mapping.
# Source: https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html
_DRIVER_CUDA_MAP: list[tuple[float, tuple[int, int]]] = [
    (570.0, (13, 0)),
    (555.0, (12, 8)),
    (550.0, (12, 6)),
    (545.0, (12, 5)),
    (535.0, (12, 4)),
    (530.0, (12, 1)),
    (525.0, (12, 0)),
    (520.0, (11, 8)),
    (515.0, (11, 7)),
]


@dataclass(frozen=True)
class GpuInfo:
    """Information about a detected NVIDIA GPU."""

    name: str
    vram_gib: int
    cuda_version: tuple[int, int] | None = None
    compute_capability: tuple[int, int] | None = None


def get_compute_capability() -> tuple[int, int] | None:
    """Query the compute capability of the first NVIDIA GPU.

    Uses ``nvidia-smi`` to retrieve the GPU's SM architecture
    (e.g. ``8.9`` for Ada Lovelace, ``10.0`` for Blackwell).

    Returns:
        ``(major, minor)`` tuple (e.g. ``(8, 9)``), or ``None``.
    """
    try:
        result = subprocess.run(  # returncode checked below
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        cap_str = result.stdout.strip().split("\n")[0].strip()
        parts = cap_str.split(".")
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
        return None

    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        return None


def detect_cuda_version() -> tuple[int, int] | None:
    """Detect CUDA version from the NVIDIA driver.

    Queries the driver version via ``nvidia-smi`` and maps it to the
    maximum supported CUDA toolkit version.

    Returns:
        ``(major, minor)`` tuple (e.g. ``(13, 0)``), or ``None``.
    """
    try:
        result = subprocess.run(  # returncode checked below
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        driver_str = result.stdout.strip().split("\n")[0].strip()
        driver_major = float(driver_str.split(".")[0])

        for min_driver, cuda_ver in _DRIVER_CUDA_MAP:
            if driver_major >= min_driver:
                return cuda_ver

        return None

    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, OSError):
        return None


def detect_nvidia_gpu(log: InstallerLogger | None = None) -> bool:
    """
    Check for the presence of an NVIDIA GPU.

    Returns:
        True if an NVIDIA GPU is detected, False otherwise.
    """
    if log is None:
        log = get_logger()
    log.item("Checking for NVIDIA GPU...")

    try:
        result = subprocess.run(  # returncode checked below
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


def check_amd_gpu(log: InstallerLogger | None = None) -> bool:
    """
    Check for the presence of an AMD GPU using OS-native commands.

    Returns:
        True if an AMD GPU is detected, False otherwise.
    """
    import platform

    if log is None:
        log = get_logger()
    log.item("Checking for AMD GPU...")

    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"],
                capture_output=True, text=True, check=True, timeout=10
            )
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            for line in lines:
                if "AMD" in line.upper() or "RADEON" in line.upper():
                    log.sub(f"AMD GPU detected: {line}", style="success")
                    return True
            return False
        except Exception:
            return False

    elif platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["lspci"],
                capture_output=True, text=True, check=True, timeout=10
            )
            is_amd = "Advanced Micro Devices" in result.stdout or "AMD" in result.stdout
            if is_amd:
                log.sub("AMD GPU detected.", style="success")
            return is_amd
        except Exception:
            return False

    return False


def get_gpu_vram_info() -> GpuInfo | None:
    """
    Query NVIDIA GPU name and total VRAM.

    Returns:
        GpuInfo object with name, VRAM in GiB, and CUDA version, or None.
    """
    try:
        result = subprocess.run(  # returncode checked below
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
        cuda = detect_cuda_version()
        cc = get_compute_capability()

        return GpuInfo(name=name, vram_gib=memory_gib, cuda_version=cuda, compute_capability=cc)

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


def cuda_tag_from_version(cuda: tuple[int, int] | None) -> str | None:
    """Map a CUDA version tuple to a supported cuda tag.

    Args:
        cuda: ``(major, minor)`` tuple, e.g. ``(13, 0)``.

    Returns:
        A tag like ``"cu130"`` or ``"cu128"``, or ``None`` if unsupported.
    """
    if cuda is None:
        return None
    major, minor = cuda
    if major >= 13:
        return "cu130"
    if major == 12 and minor >= 8:
        return "cu128"
    # Older CUDA — not supported
    return None


def display_gpu_recommendations(log: InstallerLogger | None = None) -> GpuInfo | None:
    """
    Detect GPU and display VRAM-based model recommendations.

    Returns:
        The detected GpuInfo or None.
    """
    if log is None:
        log = get_logger()

    log.log("─" * 70, level=-2)
    log.item("Checking for NVIDIA GPU to provide model recommendations...", style="warning")

    gpu = get_gpu_vram_info()
    if gpu:
        log.item(f"GPU: {gpu.name}", style="success")
        log.item(f"VRAM: {gpu.vram_gib} GB", style="success")
        if gpu.cuda_version:
            log.item(f"CUDA: {gpu.cuda_version[0]}.{gpu.cuda_version[1]}", style="success")
        rec = recommend_model_quality(gpu.vram_gib)
        log.item(f"Recommendation: {rec}", style="cyan")
    else:
        if check_amd_gpu():
            log.item("AMD GPU detected.", style="success")
            log.item("Recommendation: GGUF models are generally recommended for AMD "
                     "without custom optimization.", style="cyan")
        else:
            log.item("No NVIDIA or AMD GPU detected. Please choose based on your hardware.", style="info")

    log.log("─" * 70, level=-2)
    return gpu


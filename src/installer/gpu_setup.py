"""
GPU detection and selection for the installation process.

Extracted from ``install.py`` step 6b to keep the orchestrator clean
and make the GPU selection logic independently testable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.enums import InstallerFatalError
from src.utils.gpu import check_amd_gpu, cuda_tag_from_version, detect_cuda_version
from src.utils.prompts import confirm

if TYPE_CHECKING:
    from src.config import DependenciesConfig
    from src.platform.base import Platform
    from src.utils.logging import InstallerLogger


def detect_and_select_gpu(
    platform: Platform,
    deps: DependenciesConfig,
    log: InstallerLogger,
    *,
    cuda_override: str = "",
) -> str | None:
    """Detect GPU hardware and return the appropriate cuda tag.

    Evaluates the following in order:

    1. **Manual override** — if *cuda_override* is provided, use it as-is.
    2. **macOS** — returns ``None`` (Apple Silicon uses MPS, no tag needed).
    3. **NVIDIA CUDA** — queries the driver via ``nvidia-smi``, maps to
       ``cu130`` or ``cu128``.
    4. **AMD GPU** — returns ``rocm71`` (Linux) or ``directml`` (Windows).
    5. **No GPU** — asks the user to confirm CPU-only, returns ``"cpu"``
       or raises :class:`InstallerFatalError` if declined.

    Args:
        platform: The current platform instance.
        deps: Loaded dependencies config (for supported CUDA tags).
        log: The installer logger.
        cuda_override: Manual CUDA tag (e.g. ``"cu130"``). If non-empty,
            skips all detection.

    Returns:
        A cuda tag string (``"cu130"``, ``"cu128"``, ``"rocm71"``,
        ``"directml"``, ``"cpu"``) or ``None`` for macOS/MPS.

    Raises:
        InstallerFatalError: If no GPU is found and the user declines
            CPU-only installation.
    """
    # 1. Manual override
    if cuda_override:
        log.sub(f"Using manual GPU override: {cuda_override}", style="success")
        return cuda_override

    # 2. macOS → MPS (no cuda tag)
    if platform.name == "macos":
        log.sub("macOS detected — skipping GPU detection (using MPS).", style="info")
        return None

    # 3. NVIDIA detection
    cuda_version_detected = detect_cuda_version()
    cuda_tag = cuda_tag_from_version(cuda_version_detected)
    supported = deps.pip_packages.supported_cuda_tags

    if cuda_tag and cuda_tag in supported:
        log.sub(
            f"NVIDIA CUDA {cuda_version_detected[0]}.{cuda_version_detected[1]}"
            f" detected → using {cuda_tag}", style="success",
        )
        return cuda_tag

    if cuda_version_detected:
        # Has NVIDIA, but toolkit version unsupported
        log.warning(
            f"NVIDIA CUDA {cuda_version_detected[0]}.{cuda_version_detected[1]} detected (tag: {cuda_tag}) "
            f"but not in supported list: {', '.join(supported)}. (Falling back to cu130)",
            level=1,
        )
        return "cu130"

    # 4. AMD detection
    if check_amd_gpu():
        log.sub("AMD GPU detected.", style="success")
        if platform.name == "linux":
            cuda_tag = "rocm71"
            log.sub(f"Using Linux AMD configuration: {cuda_tag}", style="cyan")
        else:
            cuda_tag = "directml"
            log.sub(f"Using Windows AMD configuration: {cuda_tag}", style="cyan")
        return cuda_tag

    # 5. No GPU — CPU fallback
    log.warning("No NVIDIA or AMD GPU detected.", level=1)
    if not confirm("Continue anyway? (PyTorch will install CPU-only without GPU support)", default=True):
        raise InstallerFatalError("No physical GPU detected. Aborting.")
    return "cpu"

"""
Performance optimizations — Step 10.

Installs GPU acceleration libraries from a config-driven package list.

Each package in ``dependencies.json`` → ``optimizations.packages[]`` declares:
- **requires**: environment filters (e.g. ``["nvidia", "linux"]``)
- **pypi_package**: pip name, optionally per-platform
- **torch_constraints**: version-aware pip specifiers
- **install_options / retry_options**: ``uv pip install`` flags

Skipped entirely if no NVIDIA GPU is detected (all current packages
require ``"nvidia"`` in their ``requires`` list).

No external scripts are downloaded or executed.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from typing import TYPE_CHECKING

from src.utils.commands import CommandError
from src.utils.gpu import detect_nvidia_gpu
from src.utils.packaging import uv_install

if TYPE_CHECKING:
    from pathlib import Path

    from src.config import DependenciesConfig, OptimizationPackage
    from src.utils.logging import InstallerLogger


# ---------------------------------------------------------------------------
# Introspection helpers (unchanged)
# ---------------------------------------------------------------------------
def _check_package_installed(python_exe: Path, package: str) -> str | None:
    """Check whether a pip package is installed.

    Args:
        python_exe: Path to the venv Python executable.
        package: Package name to check (e.g. ``"triton"``).

    Returns:
        Installed version string, or ``None`` if not installed.
    """
    result = subprocess.run(  # returncode checked below
        [str(python_exe), "-c",
         f"from importlib.metadata import version; print(version('{package}'))"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _get_cuda_version_from_torch(python_exe: Path) -> str | None:
    """Detect CUDA version from the installed PyTorch build.

    Args:
        python_exe: Path to the venv Python executable.

    Returns:
        CUDA version string (e.g. ``"12.8"``), or ``None``.
    """
    result = subprocess.run(  # returncode checked below
        [str(python_exe), "-c",
         "import torch; print(torch.version.cuda or '')"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        ver = result.stdout.strip()
        return ver if ver else None
    return None


def _get_torch_version(python_exe: Path) -> str | None:
    """Get the installed PyTorch version string.

    Args:
        python_exe: Path to the venv Python executable.

    Returns:
        Version string (e.g. ``"2.8.0+cu128"``), or ``None``.
    """
    result = subprocess.run(  # returncode checked below
        [str(python_exe), "-c", "import torch; print(torch.__version__)"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


# ---------------------------------------------------------------------------
# Filter + constraint logic
# ---------------------------------------------------------------------------
_PLATFORM_MAP = {"win32": "windows", "linux": "linux", "darwin": "macos"}


def _get_current_platform() -> str:
    """Map ``sys.platform`` to a short name used in config."""
    return _PLATFORM_MAP.get(sys.platform, sys.platform)


def _check_requirements(
    requires: list[str],
    *,
    has_nvidia: bool,
    has_amd: bool = False,
    platform: str,
) -> bool:
    """Evaluate a package's ``requires`` filters against the environment.

    Args:
        requires: List of tags (e.g. ``["nvidia", "linux"]``).
        has_nvidia: Whether an NVIDIA GPU was detected.
        has_amd: Whether an AMD GPU was detected.
        platform: Current platform (``"windows"``, ``"linux"``, ``"macos"``).

    Returns:
        ``True`` if **all** requirements are met.
    """
    env = {platform}
    if has_nvidia:
        env.add("nvidia")
    if has_amd:
        env.add("amd")
    return all(r in env for r in requires)


def _resolve_torch_constraint(
    torch_ver: str,
    constraints: dict[str, str],
) -> str:
    """Map a PyTorch version to a compatible pip specifier.

    Tries ``"major.minor"`` key first, then falls back to the hardcoded
    table (kept for safety when a user has no ``torch_constraints``).

    Args:
        torch_ver: PyTorch version string (e.g. ``"2.10.0+cu130"``).
        constraints: Config-driven ``torch_constraints`` dict.

    Returns:
        PEP 440 version specifier (e.g. ``">=3.5,<4"``), or ``""``.
    """
    try:
        parts = torch_ver.split(".")
        major = int(parts[0])
        minor = int(parts[1].split("+")[0])
        key = f"{major}.{minor}"

        # Config-driven first
        if key in constraints:
            return constraints[key]

        # Hardcoded fallback (Triton compat table)
        if (major, minor) >= (2, 9):
            return ">=3.5,<4"
        elif (major, minor) >= (2, 8):
            return ">=3.4,<3.5"
        elif (major, minor) >= (2, 7):
            return ">=3.3,<3.4"
        elif (major, minor) >= (2, 6):
            return ">=3.2,<3.3"
        else:
            return "<3.2"
    except (ValueError, IndexError):
        return ""


# ---------------------------------------------------------------------------
# Single-package installer
# ---------------------------------------------------------------------------
def _install_package(
    pkg: OptimizationPackage,
    python_exe: Path,
    platform: str,
    torch_ver: str | None,
    log: InstallerLogger,
) -> None:
    """Install a single optimization package.

    Handles: platform-specific name resolution, torch constraints,
    install options, and retry logic.
    """
    pkg_name = pkg.get_package_name(platform)
    if pkg_name is None:
        log.info(f"{pkg.name}: not available on {platform}.")
        return

    # Check if already installed
    installed_ver = _check_package_installed(python_exe, pkg_name)
    # For triton-windows, also check under "triton"
    if installed_ver is None and pkg_name.endswith("-windows"):
        installed_ver = _check_package_installed(python_exe, pkg_name.removesuffix("-windows"))

    if installed_ver:
        log.sub(f"{pkg.name} already installed: v{installed_ver}", style="success")
        return

    # Build version constraint from torch if applicable
    constraint = ""
    if pkg.torch_constraints and torch_ver:
        constraint = _resolve_torch_constraint(torch_ver, pkg.torch_constraints)
        if constraint:
            log.sub(f"PyTorch {torch_ver} → {pkg.name} constraint: {constraint}")

    package_spec = f"{pkg_name}{constraint}" if constraint else pkg_name
    log.sub(f"Installing {package_spec}...")

    # First attempt
    try:
        uv_install(
            python_exe,
            [package_spec],
            no_build_isolation=pkg.install_options.no_build_isolation,
            no_deps=pkg.install_options.no_deps,
            ignore_errors=True,
            timeout=300,
        )
    except CommandError:
        log.info(f"{pkg.name}: first attempt failed.")

    # Verify after first attempt
    installed_ver = _check_package_installed(python_exe, pkg_name)
    if installed_ver is None and pkg_name.endswith("-windows"):
        installed_ver = _check_package_installed(python_exe, pkg_name.removesuffix("-windows"))

    if installed_ver:
        log.sub(f"{pkg.name} installed: v{installed_ver}", style="success")
        return

    # Retry with retry_options if defined
    if pkg.retry_options is not None:
        log.sub(f"Retrying {pkg.name} with fallback options...", style="yellow")
        with contextlib.suppress(CommandError):
            uv_install(
                python_exe,
                [package_spec],
                no_build_isolation=pkg.retry_options.no_build_isolation,
                no_deps=pkg.retry_options.no_deps,
                ignore_errors=True,
                timeout=300,
            )

        installed_ver = _check_package_installed(python_exe, pkg_name)
        if installed_ver:
            log.sub(f"{pkg.name} installed (retry): v{installed_ver}", style="success")
            return

    log.warning(f"{pkg.name} could not be installed.", level=2)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def install_optimizations(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install GPU optimization packages from the config-driven list.

    Iterates over ``deps.optimizations.packages``, filters by platform
    and GPU, and installs each compatible package via ``uv``.

    Skipped entirely if no NVIDIA GPU is detected (all current packages
    require ``"nvidia"``).

    Args:
        python_exe: Path to the venv Python executable.
        comfy_path: ComfyUI repository directory.
        install_path: Root installation directory.
        deps: Parsed ``dependencies.json``.
        log: Installer logger for user-facing messages.
    """
    has_nvidia = detect_nvidia_gpu()

    if not has_nvidia:
        log.info("No NVIDIA GPU — skipping GPU optimizations.")
        return

    platform = _get_current_platform()

    # Gather the list of packages from config
    packages: list[OptimizationPackage] = []
    if deps.optimizations:
        packages = deps.optimizations.packages

    if not packages:
        log.info("No optimization packages configured.")
        return

    log.item("Installing GPU optimization packages...")

    # Set CUDA_HOME if available
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        os.environ["CUDA_HOME"] = cuda_path

    # Detect torch version once for all packages
    cuda_ver = _get_cuda_version_from_torch(python_exe)
    if cuda_ver:
        log.sub(f"CUDA {cuda_ver} detected from torch.", style="success")
    else:
        log.warning("Could not detect CUDA from torch.", level=2)

    torch_ver = _get_torch_version(python_exe)

    # Install each compatible package
    for pkg in packages:
        if not _check_requirements(
            pkg.requires,
            has_nvidia=has_nvidia,
            platform=platform,
        ):
            log.info(f"{pkg.name}: skipped (requires {pkg.requires}, env={platform}).")
            continue

        _install_package(pkg, python_exe, platform, torch_ver, log)

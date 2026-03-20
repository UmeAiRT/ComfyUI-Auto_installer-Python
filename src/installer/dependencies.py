"""
Python dependency management — Steps 7-9.

Installs all Python packages required by ComfyUI:

- **Core** (Step 7): PyTorch with CUDA index, ComfyUI
  ``requirements.txt``.
- **Standard + Wheels** (Step 8): additional packages and
  pre-built ``.whl`` files (e.g. Nunchaku, InsightFace).
- **Custom Nodes** (Step 9): delegates to :mod:`src.installer.nodes`
  for Git-clone-based node installation.

All installs use ``uv`` — no raw pip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.download import download_file
from src.utils.packaging import uv_install

if TYPE_CHECKING:
    from pathlib import Path

    from src.config import DependenciesConfig
    from src.utils.logging import InstallerLogger


def install_core_dependencies(
    python_exe: Path,
    comfy_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install PyTorch and ComfyUI requirements.

    Performs two sub-steps:

    1. Install PyTorch packages from the CUDA index URL.
    2. Install ComfyUI's own ``requirements.txt``.

    Args:
        python_exe: Path to the venv Python executable.
        comfy_path: ComfyUI repository directory.
        deps: Parsed ``dependencies.json``.
        log: Installer logger for user-facing messages.
    """

    # PyTorch
    torch_pkgs = deps.pip_packages.torch.packages.split()
    log.item(f"Installing PyTorch ({', '.join(torch_pkgs)})...")
    uv_install(
        python_exe,
        torch_pkgs,
        index_url=deps.pip_packages.torch.index_url,
    )

    # ComfyUI requirements
    req_file = comfy_path / deps.pip_packages.comfyui_requirements
    if req_file.exists():
        log.item("Installing ComfyUI requirements...")
        uv_install(python_exe, requirements=req_file)


def install_python_packages(
    python_exe: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install additional standard packages listed in *deps*.

    Args:
        python_exe: Path to the venv Python executable.
        deps: Parsed ``dependencies.json``.
        log: Installer logger for user-facing messages.
    """

    if deps.pip_packages.standard:
        log.item(f"Installing {len(deps.pip_packages.standard)} standard packages...")
        uv_install(python_exe, deps.pip_packages.standard)


def install_wheels(
    python_exe: Path,
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Download and install pre-built ``.whl`` packages.

    Detects the Python version from the venv and picks the matching
    wheel for each entry.  Each wheel is downloaded to ``scripts/``,
    installed via uv, then deleted to save disk space.

    Args:
        python_exe: Path to the venv Python executable.
        install_path: Root installation directory.
        deps: Parsed ``dependencies.json``.
        log: Installer logger for user-facing messages.
    """
    if not deps.pip_packages.wheels:
        return

    # Detect Python version from the venv
    import subprocess
    result = subprocess.run(
        [str(python_exe), "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
        capture_output=True, text=True, timeout=10,
    )
    parts = result.stdout.strip().split()
    py_version = (int(parts[0]), int(parts[1])) if len(parts) == 2 else (3, 13)
    log.info(f"Python version detected: {py_version[0]}.{py_version[1]}")

    log.item(f"Installing {len(deps.pip_packages.wheels)} wheel packages...")
    scripts_dir = install_path / "scripts"

    for wheel in deps.pip_packages.wheels:
        resolved = wheel.resolve(py_version)
        if resolved is None:
            log.warning(
                f"No wheel available for {wheel.name} on Python {py_version[0]}.{py_version[1]}, skipping.",
                level=2,
            )
            continue

        whl_name, whl_url = resolved
        wheel_path = scripts_dir / f"{whl_name}.whl"
        log.sub(f"Installing {whl_name}...")

        try:
            download_file(whl_url, wheel_path)
            uv_install(python_exe, [str(wheel_path)], ignore_errors=True)
        except Exception as e:
            log.warning(f"Failed to install {whl_name}: {e}", level=3)
        finally:
            wheel_path.unlink(missing_ok=True)




def install_custom_nodes(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    log: InstallerLogger,
    *,
    node_tier: str = "full",
) -> None:
    """Install custom nodes from ``custom_nodes.json`` (additive-only).

    Resolves the manifest from ``install_path/scripts/`` or from the
    source scripts directory if not found locally. Delegates the actual
    clone + requirements install to :func:`nodes.install_all_nodes`.

    Also provisions ``nunchaku_versions.json`` into the Nunchaku node
    directory if both files exist.

    Args:
        python_exe: Path to the venv Python executable.
        comfy_path: ComfyUI repository directory.
        install_path: Root installation directory.
        log: Installer logger for user-facing messages.
        node_tier: Bundle tier — ``"minimal"``, ``"umeairt"``,
            or ``"full"`` (default).
    """
    from src.installer.environment import find_source_scripts
    from src.installer.nodes import filter_by_tier, install_all_nodes, load_manifest

    scripts_dir = install_path / "scripts"
    custom_nodes_dir = comfy_path / "custom_nodes"

    # Try to load manifest: install_path/scripts/ first, then source scripts
    manifest_path = scripts_dir / "custom_nodes.json"
    if not manifest_path.exists():
        source_dir = find_source_scripts()
        if source_dir:
            manifest_path = source_dir / "custom_nodes.json"

    if not manifest_path.exists():
        log.warning("custom_nodes.json not found. Skipping node installation.", level=1)
        return

    manifest = load_manifest(manifest_path)
    manifest = filter_by_tier(manifest, node_tier)
    install_all_nodes(manifest, custom_nodes_dir, python_exe, log)

    # Copy nunchaku_versions.json into the nunchaku node directory
    # (the node expects it in its own folder, not in scripts/)
    nunchaku_src = scripts_dir / "nunchaku_versions.json"
    if not nunchaku_src.exists():
        source_dir = find_source_scripts()
        if source_dir:
            nunchaku_src = source_dir / "nunchaku_versions.json"

    nunchaku_dst = custom_nodes_dir / "ComfyUI-nunchaku" / "nunchaku_versions.json"
    if nunchaku_src.exists() and nunchaku_dst.parent.exists():
        import shutil
        shutil.copy2(nunchaku_src, nunchaku_dst)
        log.sub("  nunchaku_versions.json provisioned.", style="success")

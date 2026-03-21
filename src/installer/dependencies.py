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
    *,
    cuda_tag: str | None,
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
        cuda_tag: CUDA tag to select PyTorch variant, e.g. ``"cu130"``.
    """

    # For macOS (MPS/CPU), install standard torch from PyPI without index_url
    if cuda_tag is None:
        # Derive package names from any available torch config, stripping +cuXXX suffixes
        any_torch = next(
            (deps.pip_packages.get_torch(t) for t in deps.pip_packages.supported_cuda_tags
             if deps.pip_packages.get_torch(t) is not None),
            None,
        )
        if any_torch is None:
            log.warning("No PyTorch configuration found in dependencies.json.", level=1)
            return
        torch_pkgs = [p.split("+")[0].split("==")[0] for p in any_torch.packages.split()]
        log.item(f"Installing PyTorch ({', '.join(torch_pkgs)}) [macOS/CPU]...")
        uv_install(python_exe, torch_pkgs)

    # For Windows/Linux with CUDA
    else:
        torch_cfg = deps.pip_packages.get_torch(cuda_tag)
        if torch_cfg is None:
            log.warning(f"No PyTorch config found for CUDA tag '{cuda_tag}'. Skipping.", level=1)
            return

        torch_pkgs = torch_cfg.packages.split()
        log.item(f"Installing PyTorch ({', '.join(torch_pkgs)}) [{cuda_tag}]...")
        uv_install(
            python_exe,
            torch_pkgs,
            index_url=torch_cfg.index_url,
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
    *,
    cuda_tag: str | None = None,
) -> None:
    """Install additional standard packages listed in *deps*.

    Args:
        python_exe: Path to the venv Python executable.
        deps: Parsed ``dependencies.json``.
        log: Installer logger for user-facing messages.
        cuda_tag: GPU configuration tag to conditionally filter packages.
    """

    if deps.pip_packages.standard:
        pkgs = deps.pip_packages.standard.copy()

        # Filter out CUDA-specific logic if not using NVIDIA (macOS or AMD)
        if cuda_tag is None or not cuda_tag.startswith("cu"):
            log.info("Filtering out CUDA-only standard packages (non-NVIDIA environment).")
            pkgs = [p for p in pkgs if not p.startswith("cupy-cuda")]
            if "onnxruntime-gpu" in pkgs:
                if cuda_tag == "directml":
                    pkgs[pkgs.index("onnxruntime-gpu")] = "onnxruntime-directml"
                else:
                    pkgs[pkgs.index("onnxruntime-gpu")] = "onnxruntime"

        log.item(f"Installing {len(pkgs)} standard packages...")
        uv_install(python_exe, pkgs)


def install_wheels(
    python_exe: Path,
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
    *,
    cuda_tag: str | None = None,
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
        cuda_tag: CUDA tag for CUDA-aware wheel selection.
    """
    if not deps.pip_packages.wheels:
        return

    # Detect Python version from the venv
    from src.utils.python_info import detect_venv_python_version
    py_version = detect_venv_python_version(python_exe)
    log.info(f"Python version detected: {py_version[0]}.{py_version[1]}")

    log.item(f"Installing {len(deps.pip_packages.wheels)} wheel packages...")
    scripts_dir = install_path / "scripts"

    for wheel in deps.pip_packages.wheels:
        if wheel.name == "nunchaku":
            from src.platform.base import get_platform
            if get_platform().name != "windows":
                log.sub("Skipping nunchaku wheel (Manifest contains Windows-only wheels).", style="cyan")
                continue
            if cuda_tag is None or not cuda_tag.startswith("cu"):
                log.sub("Skipping nunchaku wheel (NVIDIA GPU required).", style="cyan")
                continue

        resolved = wheel.resolve(py_version, cuda_tag=cuda_tag)
        if resolved is None:
            log.warning(
                f"No wheel available for {wheel.name} on Python {py_version[0]}.{py_version[1]}, skipping.",
                level=2,
            )
            continue

        whl_name, whl_url, whl_checksum = resolved
        wheel_path = scripts_dir / f"{whl_name}.whl"
        log.sub(f"Installing {whl_name}...")

        try:
            download_file(whl_url, wheel_path, checksum=whl_checksum)
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
    source_dir: Path | None = None,
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
        source_dir: Pre-resolved source scripts directory. If ``None``,
            falls back to calling :func:`find_source_scripts`.
    """
    from src.installer.nodes import filter_by_tier, install_all_nodes, load_manifest

    scripts_dir = install_path / "scripts"
    custom_nodes_dir = comfy_path / "custom_nodes"

    # Resolve source_dir lazily if not provided
    if source_dir is None:
        from src.installer.environment import find_source_scripts
        try:
            source_dir = find_source_scripts()
        except FileNotFoundError:
            source_dir = None

    # Try to load manifest: install_path/scripts/ first, then source scripts
    manifest_path = scripts_dir / "custom_nodes.json"
    if not manifest_path.exists() and source_dir:
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
    if not nunchaku_src.exists() and source_dir:
        nunchaku_src = source_dir / "nunchaku_versions.json"

    nunchaku_dst = custom_nodes_dir / "ComfyUI-nunchaku" / "nunchaku_versions.json"
    if nunchaku_src.exists() and nunchaku_dst.parent.exists():
        import shutil
        shutil.copy2(nunchaku_src, nunchaku_dst)
        log.sub("  nunchaku_versions.json provisioned.", style="success")

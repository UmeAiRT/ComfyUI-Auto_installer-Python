"""
Phase 2: ComfyUI Installation and Configuration.

Migrates Install-ComfyUI-Phase2.ps1 to Python.
Handles:
- Cloning ComfyUI repository
- Junction-based external folder architecture
- Core Python dependencies (pip, torch, xformers)
- Custom nodes installation via ComfyUI-Manager CLI
- Triton / SageAttention installation
- Optional model pack downloads
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from src import __version__
from src.config import DependenciesConfig, InstallerSettings, load_dependencies, load_settings
from src.platform.base import get_platform
from src.utils.commands import CommandError, run_and_log
from src.utils.download import download_file
from src.utils.gpu import detect_nvidia_gpu
from src.utils.logging import InstallerLogger, get_logger, setup_logger
from src.utils.prompts import confirm


# Folders managed by the junction architecture
EXTERNAL_FOLDERS = ["custom_nodes", "models", "output", "input", "user"]


def setup_git_config(log: InstallerLogger) -> None:
    """Configure Git for long paths."""
    log.item("Configuring Git for long paths...")
    try:
        run_and_log("git", ["config", "--global", "core.longpaths", "true"], ignore_errors=True)
        log.sub("Git long paths configured.", style="success")
    except CommandError:
        log.warning("Could not set git config (might need admin).", level=2)


def clone_comfyui(
    install_path: Path,
    comfy_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Clone the ComfyUI repository."""
    log.step("Cloning ComfyUI")

    if comfy_path.exists():
        log.sub("ComfyUI directory already exists.", style="success")
        return

    repo_url = deps.repositories.comfyui.url
    log.item(f"Cloning from {repo_url}...")
    run_and_log("git", ["clone", repo_url, str(comfy_path)])

    if not comfy_path.exists():
        log.error("ComfyUI cloning failed!")
        raise SystemExit(1)

    log.sub("ComfyUI cloned successfully.", style="success")


def setup_junction_architecture(
    install_path: Path,
    comfy_path: Path,
    log: InstallerLogger,
) -> None:
    """
    Set up the external folder architecture with junctions/symlinks.

    This is the core innovation of the installer — keeping user data
    outside the ComfyUI repo for clean updates.
    """
    log.step("Configuring External Folders Architecture")

    platform = get_platform()

    for folder in EXTERNAL_FOLDERS:
        external_path = install_path / folder
        internal_path = comfy_path / folder

        if internal_path.exists() and not platform.is_link(internal_path):
            # Real directory from git clone exists
            if not external_path.exists():
                # Case 1: Move default structure to external
                log.item(f"Moving '{folder}' to external location...")
                shutil.move(str(internal_path), str(external_path))
            else:
                # Case 2: External exists (previous install) — merge, then delete internal
                log.item(f"External '{folder}' detected. Merging default structure...")
                shutil.copytree(str(internal_path), str(external_path), dirs_exist_ok=True)
                shutil.rmtree(str(internal_path))
        elif not external_path.exists():
            # Case 3: Neither exist — create external
            external_path.mkdir(parents=True, exist_ok=True)

        # Create junction/symlink
        if not internal_path.exists():
            platform.create_link(internal_path, external_path)


def install_core_dependencies(
    python_exe: Path,
    comfy_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install core Python dependencies (pip, torch, ComfyUI requirements)."""
    log.step("Installing Core Dependencies")

    # Ninja (build tool)
    log.item("Checking for ninja...")
    r = subprocess.run(
        [str(python_exe), "-m", "pip", "show", "ninja"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        log.sub("Installing ninja...")
        run_and_log(str(python_exe), ["-m", "pip", "install", "ninja"])

    # Upgrade pip and wheel
    upgrade_pkgs = " ".join(deps.pip_packages.upgrade)
    log.item(f"Upgrading {upgrade_pkgs}...")
    run_and_log(
        str(python_exe),
        ["-m", "pip", "install", "--upgrade"] + deps.pip_packages.upgrade,
    )

    # PyTorch
    torch_pkgs = deps.pip_packages.torch.packages.split()
    log.item(f"Installing PyTorch ({', '.join(torch_pkgs)})...")
    run_and_log(
        str(python_exe),
        ["-m", "pip", "install"] + torch_pkgs
        + ["--index-url", deps.pip_packages.torch.index_url],
    )

    # ComfyUI requirements
    req_file = comfy_path / deps.pip_packages.comfyui_requirements
    if req_file.exists():
        log.item("Installing ComfyUI requirements...")
        run_and_log(str(python_exe), ["-m", "pip", "install", "-r", str(req_file)])


def install_python_packages(
    python_exe: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install standard Python packages."""
    log.step("Installing Python Dependencies")

    if deps.pip_packages.standard:
        log.item(f"Installing {len(deps.pip_packages.standard)} standard packages...")
        run_and_log(
            str(python_exe),
            ["-m", "pip", "install"] + deps.pip_packages.standard,
        )


def install_custom_nodes(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Install custom nodes from the JSON manifest (additive-only)."""
    from src.installer.nodes import install_all_nodes, load_manifest

    scripts_dir = install_path / "scripts"
    custom_nodes_dir = comfy_path / "custom_nodes"

    # Try to load manifest
    manifest_path = scripts_dir / "custom_nodes.json"
    if not manifest_path.exists():
        log.warning("custom_nodes.json not found. Skipping node installation.", level=1)
        return

    manifest = load_manifest(manifest_path)
    install_all_nodes(manifest, custom_nodes_dir, python_exe, log)


def install_wheels(
    python_exe: Path,
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install additional packages from .whl files."""
    if not deps.pip_packages.wheels:
        return

    log.item(f"Installing {len(deps.pip_packages.wheels)} wheel packages...")
    scripts_dir = install_path / "scripts"

    for wheel in deps.pip_packages.wheels:
        wheel_path = scripts_dir / f"{wheel.name}.whl"
        log.sub(f"Installing {wheel.name}...")

        try:
            download_file(wheel.url, wheel_path)
            run_and_log(str(python_exe), ["-m", "pip", "install", str(wheel_path)], ignore_errors=True)
        except Exception as e:
            log.warning(f"Failed to install {wheel.name}: {e}", level=3)
        finally:
            wheel_path.unlink(missing_ok=True)


def _check_triton_installed(python_exe: Path) -> bool:
    """Check if triton is installed in the target venv."""
    import subprocess

    result = subprocess.run(
        [str(python_exe), "-c",
         "from importlib.metadata import version; version('triton-windows')"],
        capture_output=True, timeout=10,
    )
    if result.returncode == 0:
        return True

    result = subprocess.run(
        [str(python_exe), "-c",
         "from importlib.metadata import version; version('triton')"],
        capture_output=True, timeout=10,
    )
    return result.returncode == 0


def install_optimizations(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Install Triton and SageAttention optimizations."""
    if not detect_nvidia_gpu():
        log.info("No NVIDIA GPU — skipping Triton/SageAttention.")
        return

    log.item("Installing Triton and SageAttention...")

    # Check if we're in a conda environment
    is_conda = bool(os.environ.get("CONDA_PREFIX"))

    if not is_conda:
        # Venv mode: try DazzleML installer first
        installer_info = deps.files.installer_script if deps.files else None

        if installer_info and installer_info.url:
            installer_dest = install_path / installer_info.destination
            try:
                download_file(installer_info.url, installer_dest)
                run_and_log(
                    str(python_exe),
                    [str(installer_dest), "--install", "--non-interactive",
                     "--base-path", str(comfy_path), "--python", str(python_exe)],
                    ignore_errors=True,
                    timeout=600,
                )
            except Exception as e:
                log.warning(f"DazzleML installer failed: {e}", level=2)

        # Verify triton is actually installed (DazzleML may exit 0 without success)
        if not _check_triton_installed(python_exe):
            log.sub("Triton not found after script — using pip fallback...", style="yellow")
            _install_triton_sage_manual(python_exe, log)
        else:
            log.sub("Triton installed successfully.", style="success")
    else:
        _install_triton_sage_manual(python_exe, log)


def _install_triton_sage_manual(python_exe: Path, log: InstallerLogger) -> None:
    """Manual fallback for Triton + SageAttention installation."""
    # Set CUDA_HOME
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        os.environ["CUDA_HOME"] = cuda_path

    log.sub("Installing Triton...")
    run_and_log(
        str(python_exe),
        ["-m", "pip", "install", "triton-windows", "--no-warn-script-location"],
        ignore_errors=True,
    )

    log.sub("Installing SageAttention...")
    try:
        run_and_log(
            str(python_exe),
            ["-m", "pip", "install", "sageattention",
             "--no-warn-script-location", "--no-build-isolation"],
        )
    except CommandError:
        log.warning("Standard install failed. Retrying without deps...", level=2)
        run_and_log(
            str(python_exe),
            ["-m", "pip", "install", "sageattention",
             "--no-deps", "--no-warn-script-location", "--no-build-isolation"],
            ignore_errors=True,
        )


def install_comfy_settings(
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """Download custom ComfyUI settings."""
    if not deps.files or not deps.files.comfy_settings:
        return

    log.item("Downloading ComfyUI custom settings...")
    settings = deps.files.comfy_settings
    dest = install_path / settings.destination
    dest.parent.mkdir(parents=True, exist_ok=True)
    download_file(settings.url, dest)


def offer_model_downloads(
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Offer optional model pack downloads via the unified catalog."""
    log.step("Optional Model Pack Downloads")

    catalog_path = install_path / "umeairt_bundles.json"
    if not catalog_path.exists():
        # Try to find it in scripts/
        catalog_path = install_path / "scripts" / "umeairt_bundles.json"

    if not catalog_path.exists():
        log.info("No model catalog found. Skipping model downloads.")
        log.info("You can download models later with: comfyui-installer download-models")
        return

    if not confirm("Would you like to download model packs now?"):
        log.sub("Model downloads skipped. You can download later with: comfyui-installer download-models")
        return

    from src.downloader.engine import interactive_download, load_catalog

    catalog = load_catalog(catalog_path)
    models_dir = install_path / "models"
    interactive_download(catalog, models_dir)


def run_phase2(install_path: Path, python_exe: Path) -> None:
    """
    Run Phase 2 of the installation.

    Args:
        install_path: Root installation directory.
        python_exe: Path to the Python executable in the environment.
    """
    log = get_logger()
    comfy_path = install_path / "ComfyUI"
    scripts_dir = install_path / "scripts"
    deps_file = scripts_dir / "dependencies.json"

    # Load dependencies
    if not deps_file.exists():
        log.error(f"dependencies.json not found at {deps_file}")
        raise SystemExit(1)

    deps = load_dependencies(deps_file)

    # Set UTF-8 environment
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"

    # Execute installation steps
    setup_git_config(log)
    clone_comfyui(install_path, comfy_path, deps, log)
    setup_junction_architecture(install_path, comfy_path, log)
    install_core_dependencies(python_exe, comfy_path, deps, log)
    install_python_packages(python_exe, deps, log)
    install_custom_nodes(python_exe, comfy_path, install_path, log)
    install_wheels(python_exe, install_path, deps, log)
    install_optimizations(python_exe, comfy_path, install_path, deps, log)
    install_comfy_settings(install_path, deps, log)
    offer_model_downloads(install_path, log)

    log.step("Installation Complete!")
    log.success("ComfyUI and all components have been installed.", level=1)
    log.item("To start ComfyUI, run: comfyui-installer start")

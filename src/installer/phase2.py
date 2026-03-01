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

    # Copy nunchaku_versions.json into the nunchaku node directory
    # (the node expects it in its own folder, not in scripts/)
    nunchaku_src = scripts_dir / "nunchaku_versions.json"
    nunchaku_dst = custom_nodes_dir / "ComfyUI-nunchaku" / "nunchaku_versions.json"
    if nunchaku_src.exists() and nunchaku_dst.parent.exists():
        import shutil
        shutil.copy2(nunchaku_src, nunchaku_dst)
        log.sub("  nunchaku_versions.json provisioned.", style="success")


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


def _check_package_installed(python_exe: Path, package: str) -> str | None:
    """Check if a package is installed and return its version, or None."""
    result = subprocess.run(
        [str(python_exe), "-c",
         f"from importlib.metadata import version; print(version('{package}'))"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _get_cuda_version_from_torch(python_exe: Path) -> str | None:
    """Detect CUDA version from the installed torch build."""
    result = subprocess.run(
        [str(python_exe), "-c",
         "import torch; print(torch.version.cuda or '')"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        ver = result.stdout.strip()
        return ver if ver else None
    return None


def _get_torch_version(python_exe: Path) -> str | None:
    """Get the installed PyTorch version string."""
    result = subprocess.run(
        [str(python_exe), "-c", "import torch; print(torch.__version__)"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _get_triton_constraint(torch_ver: str) -> str:
    """
    Get compatible triton-windows version constraint for a PyTorch version.

    Based on triton-windows compatibility matrix:
    https://github.com/woct0rdho/triton-windows/issues/158

    Credit: DazzleML's comfyui-triton-sageattention installer
    (https://github.com/DazzleML/comfyui-triton-and-sageattention-installer)
    """
    try:
        parts = torch_ver.split(".")
        major = int(parts[0])
        minor = int(parts[1].split("+")[0])  # Handle "+cu128" suffix

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
        return ""  # No constraint if can't parse


def install_optimizations(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
) -> None:
    """
    Install Triton and SageAttention optimizations.

    Internalized logic inspired by DazzleML's comfyui-triton-sageattention
    (https://github.com/DazzleML/comfyui-triton-and-sageattention-installer).
    No external script is downloaded — all checks and installs happen locally
    using pip with explicit argument lists.
    """
    if not detect_nvidia_gpu():
        log.info("No NVIDIA GPU — skipping Triton/SageAttention.")
        return

    log.item("Installing Triton and SageAttention...")

    # Set CUDA_HOME if available
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        os.environ["CUDA_HOME"] = cuda_path

    # Detect CUDA and torch version
    cuda_ver = _get_cuda_version_from_torch(python_exe)
    if cuda_ver:
        log.sub(f"CUDA {cuda_ver} detected from torch.", style="success")
    else:
        log.warning("Could not detect CUDA from torch. Triton may not work.", level=2)

    # --- Triton ---
    import sys as _sys

    base_package = "triton-windows" if _sys.platform == "win32" else "triton"
    triton_ver = _check_package_installed(python_exe, base_package)
    if triton_ver is None and base_package == "triton-windows":
        triton_ver = _check_package_installed(python_exe, "triton")

    if triton_ver:
        log.sub(f"Triton already installed: v{triton_ver}", style="success")
    else:
        # Determine version constraint from PyTorch
        torch_ver = _get_torch_version(python_exe)
        constraint = _get_triton_constraint(torch_ver) if torch_ver else ""
        package_spec = f"{base_package}{constraint}" if constraint else base_package

        if constraint:
            log.sub(f"PyTorch {torch_ver} → Triton constraint: {constraint}")

        log.sub(f"Installing {package_spec}...")
        try:
            run_and_log(
                str(python_exe),
                ["-m", "pip", "install", package_spec,
                 "--no-warn-script-location"],
                ignore_errors=True,
                timeout=300,
            )
        except CommandError:
            log.warning(f"{base_package} install failed.", level=2)

        # Verify
        triton_ver = _check_package_installed(python_exe, base_package)
        if triton_ver is None and base_package == "triton-windows":
            triton_ver = _check_package_installed(python_exe, "triton")

        if triton_ver:
            log.sub(f"Triton installed: v{triton_ver}", style="success")
        else:
            log.warning("Triton could not be installed. SageAttention may be limited.", level=2)

    # --- SageAttention ---
    sage_ver = _check_package_installed(python_exe, "sageattention")

    if sage_ver:
        log.sub(f"SageAttention already installed: v{sage_ver}", style="success")
    else:
        log.sub("Installing SageAttention...")
        try:
            run_and_log(
                str(python_exe),
                ["-m", "pip", "install", "sageattention",
                 "--no-warn-script-location", "--no-build-isolation"],
                timeout=300,
            )
        except CommandError:
            # Retry without deps (common workaround)
            log.sub("Retrying SageAttention without deps...", style="yellow")
            run_and_log(
                str(python_exe),
                ["-m", "pip", "install", "sageattention",
                 "--no-deps", "--no-warn-script-location",
                 "--no-build-isolation"],
                ignore_errors=True,
                timeout=300,
            )

        sage_ver = _check_package_installed(python_exe, "sageattention")
        if sage_ver:
            log.sub(f"SageAttention installed: v{sage_ver}", style="success")
        else:
            log.warning("SageAttention could not be installed.", level=2)


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


def install_cli_in_environment(
    python_exe: Path,
    log: InstallerLogger,
) -> None:
    """
    Install the comfyui-installer CLI into the target environment.

    This ensures the `comfyui-installer` command is available in the venv/conda
    environment, so that generated tool scripts (Update, Download-Models) work.
    """
    log.item("Installing comfyui-installer CLI into environment...")
    installer_root = Path(__file__).resolve().parent.parent.parent
    run_and_log(
        str(python_exe),
        ["-m", "pip", "install", "-e", str(installer_root), "--quiet"],
    )
    log.sub("comfyui-installer CLI available in environment.", style="success")

def create_launchers(
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """
    Generate cross-platform launcher scripts.

    Creates two launchers:
    - Performance mode: SageAttention, listen, auto-launch
    - LowVRAM mode:    Same + lowvram + disable-smart-memory + fp8
    """
    import sys as _sys

    log.item("Creating launcher scripts...")

    is_windows = _sys.platform == "win32"

    perf_args = "--use-sage-attention --listen --auto-launch"
    lowvram_args = f"{perf_args} --disable-smart-memory --lowvram --fp8_e4m3fn-text-enc"

    launchers: list[tuple[str, str, str]] = [
        ("UmeAiRT-Start-ComfyUI", "Performance Mode", perf_args),
        ("UmeAiRT-Start-ComfyUI_LowVRAM", "Low VRAM / Stability Mode", lowvram_args),
    ]

    for name, mode_label, args in launchers:
        if is_windows:
            _write_bat_launcher(install_path, name, mode_label, args, log)
        else:
            _write_sh_launcher(install_path, name, mode_label, args, log)

    # Model download tool
    # Update tool
    if is_windows:
        tools: list[tuple[str, str, str]] = [
            ("UmeAiRT-Download-Models", "Model Downloader",
             'comfyui-installer download-models --path "%InstallPath%"'),
            ("UmeAiRT-Update", "Updater",
             'comfyui-installer update --path "%InstallPath%"'),
        ]
        for tool_name, tool_label, tool_cmd in tools:
            _write_bat_tool(install_path, tool_name, tool_label, tool_cmd, log)
    else:
        tools = [
            ("UmeAiRT-Download-Models", "Model Downloader",
             'comfyui-installer download-models --path "$SCRIPT_DIR"'),
            ("UmeAiRT-Update", "Updater",
             'comfyui-installer update --path "$SCRIPT_DIR"'),
        ]
        for tool_name, tool_label, tool_cmd in tools:
            _write_sh_tool(install_path, tool_name, tool_label, tool_cmd, log)


def _write_bat_launcher(
    install_path: Path, name: str, mode_label: str, args: str,
    log: InstallerLogger,
) -> None:
    """Write a Windows .bat launcher."""
    script_path = install_path / f"{name}.bat"
    content = f"""@echo off
setlocal
chcp 65001 > nul
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"

:: ============================================================================
:: {name}.bat — {mode_label}
:: Generated by ComfyUI Auto-Installer
:: ============================================================================

set "InstallPath=%~dp0"
if "%InstallPath:~-1%"=="\\" set "InstallPath=%InstallPath:~0,-1%"

:: --- Environment Detection ---
set "InstallType=venv"
if exist "%InstallPath%\\scripts\\install_type" (
    set /p InstallType=<"%InstallPath%\\scripts\\install_type"
)

if "%InstallType%"=="venv" (
    echo [INFO] Activating venv...
    call "%InstallPath%\\scripts\\venv\\Scripts\\activate.bat"
) else (
    echo [INFO] Activating Conda...
    call "%LOCALAPPDATA%\\Miniconda3\\Scripts\\activate.bat"
    call conda activate UmeAiRT
)

if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate environment.
    pause
    exit /b %errorlevel%
)

:: --- Launch ComfyUI ---
echo [INFO] Starting ComfyUI ({mode_label})...
cd /d "%InstallPath%\\ComfyUI"
python main.py {args}

pause
"""
    script_path.write_text(content, encoding="utf-8")
    log.sub(f"{script_path.name} created.", style="success")


def _write_sh_launcher(
    install_path: Path, name: str, mode_label: str, args: str,
    log: InstallerLogger,
) -> None:
    """Write a Linux/macOS .sh launcher."""
    script_path = install_path / f"{name}.sh"
    content = f"""#!/usr/bin/env bash
# ============================================================================
# {name}.sh — {mode_label}
# Generated by ComfyUI Auto-Installer
# ============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

# --- Environment Detection ---
INSTALL_TYPE="venv"
if [ -f "$SCRIPT_DIR/scripts/install_type" ]; then
    INSTALL_TYPE=$(cat "$SCRIPT_DIR/scripts/install_type")
fi

if [ "$INSTALL_TYPE" = "venv" ]; then
    echo "[INFO] Activating venv..."
    source "$SCRIPT_DIR/scripts/venv/bin/activate"
else
    echo "[INFO] Activating Conda..."
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate UmeAiRT
fi

# --- Launch ComfyUI ---
echo "[INFO] Starting ComfyUI ({mode_label})..."
cd "$SCRIPT_DIR/ComfyUI"
python main.py {args}
"""
    script_path.write_text(content, encoding="utf-8")
    # Make executable on Unix
    import stat
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    log.sub(f"{script_path.name} created.", style="success")


def _write_bat_tool(
    install_path: Path, name: str, label: str, command: str,
    log: InstallerLogger,
) -> None:
    """Write a Windows .bat tool script."""
    script_path = install_path / f"{name}.bat"
    content = f"""@echo off
setlocal
chcp 65001 > nul
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
set "PYTHONUTF8=1"

:: ============================================================================
:: {name}.bat — {label}
:: Generated by ComfyUI Auto-Installer
:: ============================================================================

set "InstallPath=%~dp0"
if "%InstallPath:~-1%"=="\\" set "InstallPath=%InstallPath:~0,-1%"

:: --- Environment Detection ---
set "InstallType=venv"
if exist "%InstallPath%\\scripts\\install_type" (
    set /p InstallType=<"%InstallPath%\\scripts\\install_type"
)

if "%InstallType%"=="venv" (
    call "%InstallPath%\\scripts\\venv\\Scripts\\activate.bat"
) else (
    call "%LOCALAPPDATA%\\Miniconda3\\Scripts\\activate.bat"
    call conda activate UmeAiRT
)

echo [INFO] {label}...
{command}

pause
"""
    script_path.write_text(content, encoding="utf-8")
    log.sub(f"{script_path.name} created.", style="success")


def _write_sh_tool(
    install_path: Path, name: str, label: str, command: str,
    log: InstallerLogger,
) -> None:
    """Write a Linux/macOS .sh tool script."""
    script_path = install_path / f"{name}.sh"
    content = f"""#!/usr/bin/env bash
# ============================================================================
# {name}.sh — {label}
# Generated by ComfyUI Auto-Installer
# ============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"

# --- Environment Detection ---
INSTALL_TYPE="venv"
if [ -f "$SCRIPT_DIR/scripts/install_type" ]; then
    INSTALL_TYPE=$(cat "$SCRIPT_DIR/scripts/install_type")
fi

if [ "$INSTALL_TYPE" = "venv" ]; then
    source "$SCRIPT_DIR/scripts/venv/bin/activate"
else
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate UmeAiRT
fi

echo "[INFO] {label}..."
{command}
"""
    script_path.write_text(content, encoding="utf-8")
    import stat
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    log.sub(f"{script_path.name} created.", style="success")


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
    install_cli_in_environment(python_exe, log)
    install_custom_nodes(python_exe, comfy_path, install_path, log)
    install_wheels(python_exe, install_path, deps, log)
    install_optimizations(python_exe, comfy_path, install_path, deps, log)
    install_comfy_settings(install_path, deps, log)
    create_launchers(install_path, log)
    offer_model_downloads(install_path, log)

    log.step("Installation Complete!")
    log.success("ComfyUI and all components have been installed.", level=1)
    log.item("Double-click UmeAiRT-Start-ComfyUI to launch!")

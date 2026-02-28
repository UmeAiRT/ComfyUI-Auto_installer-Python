"""
Phase 1: System Setup and Environment Preparation.

Migrates Install-ComfyUI-Phase1.ps1 to Python.
Handles:
- Admin privilege checks (long paths, VS Build Tools)
- System dependencies (Git, aria2, Python)
- Python environment creation (venv)
- Launch of Phase 2

Unlike the PowerShell version, this runs as a single unified flow
(no separate admin window / Phase 2 window needed).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from src import __version__
from src.config import InstallerSettings, load_dependencies, load_settings
from src.platform.base import get_platform
from src.utils.commands import check_command_exists, run_and_log
from src.utils.download import download_file
from src.utils.logging import InstallerLogger, get_logger, setup_logger
from src.utils.prompts import ask_choice, confirm


def check_prerequisites(log: InstallerLogger) -> bool:
    """
    Check system prerequisites (Git, Python).
    Returns True if all prerequisites are met.
    """
    log.step("Checking Prerequisites")
    all_ok = True

    # Check Git
    if check_command_exists("git"):
        git_ver = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
        log.sub(f"Git: {git_ver}", style="success")
    else:
        log.warning("Git is not installed.", level=2)
        all_ok = False

    return all_ok


def install_git(log: InstallerLogger) -> bool:
    """
    Install Git for Windows.

    Returns True on success.
    """
    if sys.platform != "win32":
        log.error("Automatic Git installation is only supported on Windows.")
        log.item("Please install Git manually: sudo apt install git (Linux) or brew install git (macOS)")
        return False

    if not confirm("Git is required. Would you like to install it automatically?"):
        log.error("Installation aborted — Git is mandatory.")
        return False

    log.item("Downloading Git for Windows...")
    git_url = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
    git_installer = Path(os.environ.get("TEMP", "/tmp")) / "git-installer.exe"

    try:
        download_file(git_url, git_installer)
        log.sub("Installing Git (accept UAC if prompted)...")

        result = subprocess.run(
            [str(git_installer), "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-",
             "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
            timeout=300,
        )

        if result.returncode == 0:
            log.success("Git installed successfully.", level=2)
            # Refresh PATH
            if sys.platform == "win32":
                os.environ["PATH"] = (
                    os.environ.get("PATH", "")
                    + ";"
                    + r"C:\Program Files\Git\cmd"
                )
            return True
        else:
            log.error(f"Git installer failed with code {result.returncode}.")
            return False
    except Exception as e:
        log.error(f"Git installation failed: {e}")
        return False
    finally:
        git_installer.unlink(missing_ok=True)


def install_aria2(log: InstallerLogger) -> bool:
    """
    Install aria2 download accelerator (Windows).

    Returns True if aria2 is available after this call.
    """
    if check_command_exists("aria2c"):
        log.sub("aria2 is already installed.", style="success")
        return True

    if sys.platform != "win32":
        log.info("aria2 auto-install is Windows-only. Please install manually.")
        return False

    log.item("Installing aria2 (download accelerator)...")
    aria2_url = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"
    local_app = Path(os.environ.get("LOCALAPPDATA", ""))
    aria2_dir = local_app / "aria2"
    aria2_exe = aria2_dir / "aria2c.exe"

    if aria2_exe.exists():
        os.environ["PATH"] = str(aria2_dir) + ";" + os.environ.get("PATH", "")
        log.sub("aria2 already installed.", style="success")
        return True

    zip_path = Path(os.environ.get("TEMP", "/tmp")) / "aria2.zip"
    try:
        download_file(aria2_url, zip_path)
        log.sub("Extracting aria2...")
        aria2_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(aria2_dir)

        # Find aria2c.exe in extracted contents
        for root, _dirs, files in os.walk(aria2_dir):
            for f in files:
                if f.lower() == "aria2c.exe":
                    src = Path(root) / f
                    if src.parent != aria2_dir:
                        shutil.move(str(src), str(aria2_exe))
                    break

        if aria2_exe.exists():
            os.environ["PATH"] = str(aria2_dir) + ";" + os.environ.get("PATH", "")
            log.sub("aria2 installed successfully.", style="success")
            return True

        log.warning("aria2c.exe not found in archive.", level=2)
        return False

    except Exception as e:
        log.warning(f"aria2 installation failed: {e}. Downloads will use standard speed.", level=2)
        return False
    finally:
        zip_path.unlink(missing_ok=True)


def setup_environment(
    install_path: Path,
    install_type: str,
    log: InstallerLogger,
) -> Path:
    """
    Create the Python environment (venv or conda).

    Args:
        install_path: Root installation directory.
        install_type: "venv" or "conda".
        log: Logger.

    Returns:
        Path to the python executable inside the environment.
    """
    scripts_dir = install_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    if install_type == "venv":
        log.step("Creating Virtual Environment (venv)")
        venv_path = scripts_dir / "venv"

        if venv_path.exists():
            log.sub("Virtual environment already exists.", style="success")
        else:
            platform = get_platform()
            python_path = platform.detect_python("3.13")

            if python_path is None:
                # Try to install Python 3.13 (no fallback — wheels are cp313 only)
                if sys.platform == "win32" and confirm("Python 3.13 not found. Install automatically?"):
                    python_path = _install_python_windows(log)

                if python_path is None:
                    log.error("Python 3.13 is required (wheels are compiled for cp313).")
                    log.item("Please install from https://www.python.org/downloads/release/python-31311/")
                    raise SystemExit(1)

            log.item(f"Creating venv with {python_path}...")
            run_and_log(str(python_path), ["-m", "venv", str(venv_path)])
            log.sub("Virtual environment created.", style="success")

        # Return the venv python
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    else:
        log.step("Setting up Miniconda Environment")
        log.warning("Conda support is planned but not yet implemented in the Python version.")
        log.item("Please use --type venv for now.")
        raise SystemExit(1)


def _install_python_windows(log: InstallerLogger) -> Path | None:
    """Install Python 3.13 on Windows. Returns path to python.exe or None."""
    py_url = "https://www.python.org/ftp/python/3.13.11/python-3.13.11-amd64.exe"
    py_installer = Path(os.environ.get("TEMP", ".")) / "python-3.13.11-amd64.exe"

    try:
        log.item("Downloading Python 3.13...")
        download_file(py_url, py_installer)

        log.sub("Installing Python (this may take a minute)...")
        result = subprocess.run(
            [str(py_installer), "/passive", "PrependPath=1",
             "Include_launcher=1", "Include_test=0"],
            timeout=300,
        )

        if result.returncode == 0:
            log.success("Python 3.13 installed.", level=2)

            # Try to find the new installation
            candidates = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python313/python.exe",
                Path("C:/Program Files/Python313/python.exe"),
            ]
            for p in candidates:
                if p.exists():
                    return p

            # Try py launcher
            if check_command_exists("py"):
                try:
                    r = subprocess.run(
                        ["py", "-3.13", "-c", "import sys; print(sys.executable)"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if r.returncode == 0:
                        return Path(r.stdout.strip())
                except Exception:
                    pass

        log.error("Python installation failed.")
        return None
    except Exception as e:
        log.error(f"Python installation error: {e}")
        return None
    finally:
        py_installer.unlink(missing_ok=True)


def _find_source_scripts() -> Path | None:
    """
    Locate the source 'scripts/' directory containing config files.

    Searches relative to the package installation, then common locations.

    Returns:
        Path to the scripts directory, or None.
    """
    # 1. Relative to this file: src/installer/phase1.py → ../../scripts/
    package_root = Path(__file__).resolve().parent.parent.parent
    candidate = package_root / "scripts"
    if (candidate / "dependencies.json").exists():
        return candidate

    # 2. Current working directory
    candidate = Path.cwd() / "scripts"
    if (candidate / "dependencies.json").exists():
        return candidate

    return None


# Files that Phase 2 needs in install_path/scripts/
ESSENTIAL_FILES = [
    "dependencies.json",
    "custom_nodes.json",
    "snapshot.json",
    "custom_nodes.csv",
    "environment.yml",
    "nunchaku_versions.json",
]


def provision_scripts(install_path: Path, log: InstallerLogger) -> None:
    """
    Copy essential config files to the install directory.

    In the PowerShell version, the user downloaded the entire repo into
    the install directory, so scripts/ was always present. In the Python
    version, the package is installed separately, so we need to copy
    the config files to install_path/scripts/.

    Args:
        install_path: Root installation directory.
        log: Logger.
    """
    log.step("Provisioning Configuration Files")

    source_dir = _find_source_scripts()
    if source_dir is None:
        log.warning("Could not find source scripts directory.", level=1)
        log.info("Looking for dependencies.json relative to the package and CWD.")
        return

    dest_dir = install_path / "scripts"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for filename in ESSENTIAL_FILES:
        src = source_dir / filename
        dst = dest_dir / filename

        if not src.exists():
            log.sub(f"  {filename}: [dim]not in source (skipped)[/dim]")
            continue

        if dst.exists():
            # Update if source is newer
            if src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)
                log.sub(f"  {filename}: updated", style="cyan")
                copied += 1
            else:
                log.sub(f"  {filename}: already up to date", style="success")
        else:
            shutil.copy2(src, dst)
            log.sub(f"  {filename}: copied", style="success")
            copied += 1

    # Also copy umeairt_bundles.json to install root for the model downloader
    bundles_src = source_dir.parent / "umeairt_bundles.json"
    if not bundles_src.exists():
        # Try in scripts/ itself
        bundles_src = source_dir / "umeairt_bundles.json"
    bundles_dst = install_path / "umeairt_bundles.json"

    if bundles_src.exists() and not bundles_dst.exists():
        shutil.copy2(bundles_src, bundles_dst)
        log.sub("  umeairt_bundles.json: copied to install root", style="success")
        copied += 1

    log.item(f"{copied} file(s) provisioned.")


def run_phase1(install_path: Path, install_type: str = "venv", *, verbose: bool = False) -> Path:
    """
    Run Phase 1 of the installation.

    Args:
        install_path: Root installation directory.
        install_type: "venv" or "conda".
        verbose: Show detailed subprocess output.

    Returns:
        Path to the python executable in the created environment.
    """
    log = setup_logger(
        log_file=install_path / "logs" / "install_log.txt",
        total_steps=9,
        verbose=verbose,
    )
    log.banner("UmeAiRT", "ComfyUI — Auto-Installer (Phase 1)", __version__)

    # Platform setup
    platform = get_platform()

    # Admin tasks (long paths)
    log.step("System Configuration")
    platform.enable_long_paths()

    # Install aria2
    install_aria2(log)

    # Check Git
    if not check_prerequisites(log):
        if not install_git(log):
            raise SystemExit(1)

    # Setup environment
    python_exe = setup_environment(install_path, install_type, log)

    # Provision config files to install directory
    provision_scripts(install_path, log)

    log.success("Phase 1 complete! Environment is ready.", level=0)
    return python_exe

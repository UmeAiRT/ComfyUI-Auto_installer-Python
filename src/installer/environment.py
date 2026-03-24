"""
Python environment and configuration provisioning — Steps 3-4.

Creates the Python virtual environment and copies the minimum
configuration files needed for the rest of the install:

- **venv creation** (Step 3): tries ``uv`` first (auto-downloads
  Python 3.11-3.13), falls back to system Python.
- **Provisioning** (Step 4): copies ``dependencies.json`` and the
  model catalog to the install directory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.enums import InstallerFatalError, InstallType
from src.platform.base import get_platform
from src.utils.commands import CommandError, check_command_exists, run_and_log
from src.utils.download import download_file
from src.utils.prompts import confirm

if TYPE_CHECKING:
    from src.config import DependenciesConfig
    from src.utils.logging import InstallerLogger


def _create_venv_with_uv(
    uv_cmd: str | Path,
    venv_path: Path,
    log: InstallerLogger,
) -> None:
    """Create a venv with uv, trying system Python first then uv-managed.

    Args:
        uv_cmd: Path or name of the uv executable.
        venv_path: Target directory for the virtual environment.
        log: Installer logger.

    Raises:
        CommandError: If both system and managed Python attempts fail.
    """
    try:
        # Prefer the user's existing system Python
        run_and_log(str(uv_cmd), ["venv", str(venv_path), "--python", ">=3.11,<3.14",
                                   "--python-preference", "only-system",
                                   "--seed", "--link-mode", "copy"])
        log.sub("Virtual environment created (system Python).", style="success")
    except CommandError:
        # No compatible system Python — let uv download one
        log.item("No compatible system Python found, downloading via uv...")
        run_and_log(str(uv_cmd), ["venv", str(venv_path), "--python", ">=3.11,<3.14",
                                   "--seed", "--link-mode", "copy"])
        log.sub("Virtual environment created (uv-managed Python).", style="success")


def setup_environment(
    install_path: Path,
    install_type: InstallType,
    log: InstallerLogger,
) -> Path:
    """Create the Python virtual environment.

    Strategy (in order):

    1. ``uv venv`` with Python >=3.11,<3.14 auto-managed.
    2. System conda (Miniconda/Anaconda) with a local prefix.
    3. System Python 3.11-3.13 (detected via platform abstraction).
    4. Auto-install Python on Windows (if user agrees).

    After creation, verifies the expected ``python`` executable
    exists inside the venv.

    Args:
        install_path: Root installation directory.
        install_type: :attr:`InstallType.VENV` or
            :attr:`InstallType.CONDA`.
        log: Installer logger for user-facing messages.

    Returns:
        Absolute path to the Python executable inside the environment.

    Raises:
        InstallerFatalError: If no usable Python 3.11+ can be found or created.
    """
    scripts_dir = install_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    log.item(f"Install path: {install_path}")

    if install_type is InstallType.VENV:
        venv_path = scripts_dir / "venv"

        if venv_path.exists():
            log.sub("Virtual environment already exists.", style="success")
        else:
            # Find uv: PATH first, then local scripts/uv/
            uv_cmd: str | Path | None = None
            if check_command_exists("uv"):
                uv_cmd = "uv"
            else:
                local_uv = scripts_dir / "uv" / ("uv.exe" if sys.platform == "win32" else "uv")
                if local_uv.exists():
                    uv_cmd = local_uv

            if uv_cmd is not None:
                log.item("Creating Python environment...")
                _create_venv_with_uv(uv_cmd, venv_path, log)

            # Fallback: use system Python if uv didn't create the venv
            if not venv_path.exists():
                platform = get_platform()
                python_path = None
                for try_version in ("3.13", "3.12", "3.11"):
                    python_path = platform.detect_python(try_version)
                    if python_path:
                        break

                if python_path is None:
                    log.error("Python 3.11+ is required but could not be acquired.")
                    log.item("If 'uv' failed, this may be due to network or Antivirus restrictions.")
                    log.item("Please install Python 3.11-3.13 from https://www.python.org/downloads/")
                    raise InstallerFatalError("Python 3.11+ is required but could not be acquired.")

                log.item(f"Creating venv with {python_path}...")
                run_and_log(str(python_path), ["-m", "venv", str(venv_path)])
                log.sub("Virtual environment created.", style="success")

        # Return the venv python and verify it exists
        if sys.platform == "win32":
            python_exe = venv_path / "Scripts" / "python.exe"
        else:
            python_exe = venv_path / "bin" / "python"

        if not python_exe.exists():
            log.error(f"Venv python not found at expected path: {python_exe}")
            log.item(f"Venv directory: {venv_path}")
            raise InstallerFatalError(f"Venv python not found at expected path: {python_exe}")

        log.sub(f"Venv python: {python_exe}", style="success")
        return python_exe

    elif install_type is InstallType.CONDA:
        conda_env_path = scripts_dir / "conda_env"

        # Determine Python executable path based on OS
        if sys.platform == "win32":
            python_exe = conda_env_path / "python.exe"
        else:
            python_exe = conda_env_path / "bin" / "python"

        if conda_env_path.exists() and python_exe.exists():
            log.sub("Conda environment already exists.", style="success")
            log.sub(f"Conda python: {python_exe}", style="success")
            return python_exe

        # Find or install Conda
        conda_exe = _find_conda(log)
        if not conda_exe:
            if sys.platform == "win32" and confirm("Conda not found. Install Miniconda automatically?"):
                conda_exe = _install_miniconda_windows(log)

            if not conda_exe:
                log.error("Conda is required for this installation type.")
                log.item("Please install Miniconda from https://docs.anaconda.com/free/miniconda/")
                raise InstallerFatalError("Conda is required for this installation type.")

        # Provision the environment.yml first so conda can use it
        provision_scripts(install_path, log)
        env_yml = scripts_dir / "environment.yml"

        if not env_yml.exists():
            log.error(f"environment.yml not found at {env_yml}")
            raise InstallerFatalError(f"environment.yml not found at {env_yml}")

        log.item(f"Creating local Conda environment at {conda_env_path}...")
        try:
            run_and_log(
                str(conda_exe),
                ["env", "create", "-p", str(conda_env_path), "-f", str(env_yml), "-y"]
            )
            log.sub("Conda environment created.", style="success")
        except CommandError:
            log.error("Failed to create Conda environment.")
            raise InstallerFatalError("Failed to create Conda environment.") from None

        if not python_exe.exists():
            log.error(f"Conda python not found at expected path: {python_exe}")
            raise InstallerFatalError(f"Conda python not found at expected path: {python_exe}")

        log.sub(f"Conda python: {python_exe}", style="success")
        return python_exe

    else:
        raise InstallerFatalError(f"Unknown install type: {install_type}")


def _find_conda(log: InstallerLogger) -> Path | None:
    """Find the conda executable in the PATH or standard locations."""
    if check_command_exists("conda"):
        log.item("Found conda in PATH.")
        import shutil
        return Path(shutil.which("conda"))

    candidates = []
    if sys.platform == "win32":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            local_app_data / "Miniconda3" / "Scripts" / "conda.exe",
            local_app_data / "anaconda3" / "Scripts" / "conda.exe",
            Path("C:/ProgramData/Miniconda3/Scripts/conda.exe"),
            Path("C:/ProgramData/anaconda3/Scripts/conda.exe"),
            Path("C:/tools/miniconda3/Scripts/conda.exe"),
        ]
    else:
        home = Path.home()
        candidates = [
            home / "miniconda3" / "bin" / "conda",
            home / "anaconda3" / "bin" / "conda",
            Path("/opt/miniconda3/bin/conda"),
        ]

    for p in candidates:
        if p.exists():
            log.item(f"Found conda at {p}")
            return p

    return None


def _install_miniconda_windows(
    log: InstallerLogger,
    deps: DependenciesConfig | None = None,
) -> Path | None:
    """Download and install Miniconda on Windows in silent mode.

    Args:
        log: Installer logger.
        deps: Optional dependencies config — if provided, uses the
            ``tools.miniconda_windows`` SHA-256 for integrity verification.
    """
    # Use config URL/hash if available, otherwise fall back to default
    if deps and deps.tools.miniconda_windows.url:
        conda_url = deps.tools.miniconda_windows.url
        expected_hash = deps.tools.miniconda_windows.sha256
    else:
        conda_url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
        expected_hash = ""

    installer_path = Path(os.environ.get("TEMP", ".")) / "Miniconda3-installer.exe"

    try:
        log.item("Downloading Miniconda...")
        download_file(conda_url, installer_path, mirrors=deps.mirrors if deps else None)

        # Verify SHA-256 integrity using the hash from dependencies.json
        if expected_hash:
            import hashlib

            actual_hash = hashlib.sha256(installer_path.read_bytes()).hexdigest().lower()
            if actual_hash != expected_hash.lower():
                log.error("Miniconda checksum verification failed! File may be corrupted.")
                installer_path.unlink(missing_ok=True)
                return None
            log.sub("Miniconda checksum verified ✓", style="success")

        install_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Miniconda3"

        log.sub("Installing Miniconda (this may take a minute)...")
        result = subprocess.run(  # returncode checked below
            [
                str(installer_path),
                "/InstallationType=JustMe",
                "/RegisterPython=0",
                "/S",
                f"/D={install_dir}"
            ],
            timeout=600,
        )

        if result.returncode == 0:
            log.success("Miniconda installed.", level=2)
            conda_exe = install_dir / "Scripts" / "conda.exe"
            if conda_exe.exists():
                # Re-init shell for conda if needed
                subprocess.run([str(conda_exe), "init"], capture_output=True)  # best-effort, ignore errors
                return conda_exe

        log.error("Miniconda silent installation failed.")
        raise OSError("Non-zero exit code or timeout from installer")
    except Exception as e:
        log.error("Miniconda installation failed, likely blocked by Windows UAC or Antivirus.")
        log.error(f"Error details: {e}")
        log.item("Please download and install Miniconda manually from:")
        log.item("https://docs.anaconda.com/free/miniconda/")
        return None
    finally:
        installer_path.unlink(missing_ok=True)


def find_source_scripts() -> Path:
    """Locate the source ``scripts/`` directory containing config files.

    Searches relative to this package: ``../../scripts/`` from ``environment.py``.
    Falls back to ``Path.cwd() / "scripts"`` to support installed environments (like CI).

    Raises:
        FileNotFoundError: If the scripts directory or dependencies.json
            is missing (enforces package integrity).
    """
    package_root = Path(__file__).resolve().parent.parent.parent
    candidate = package_root / "scripts"

    if candidate.exists() and (candidate / "dependencies.json").exists():
        return candidate

    cwd_candidate = Path.cwd() / "scripts"
    if cwd_candidate.exists() and (cwd_candidate / "dependencies.json").exists():
        return cwd_candidate

    raise FileNotFoundError(
        f"Crucial source directory missing: {candidate}. "
        "Ensure the installer is not separated from its 'scripts' directory."
    )


# Files needed to bootstrap the install (copied early).
BOOTSTRAP_FILES = [
    "dependencies.json",
]

# Files resolved on-demand from source when needed.
DEFERRED_FILES = [
    "custom_nodes.json",
    "environment.yml",
    "nunchaku_versions.json",
]


def provision_scripts(install_path: Path, log: InstallerLogger) -> None:
    """Copy bootstrap config files to the install directory.

    Only copies files listed in ``BOOTSTRAP_FILES`` (currently just
    ``dependencies.json``). Other configs like ``custom_nodes.json``
    are resolved on-demand by later steps from the source directory.

    Also copies ``model_manifest.json`` to ``install_path/scripts/``
    so the model downloader can find it.

    Args:
        install_path: Root installation directory.
        log: Installer logger for user-facing messages.
    """

    try:
        source_dir = find_source_scripts()
    except FileNotFoundError as e:
        log.error(str(e))
        raise InstallerFatalError(str(e)) from None

    dest_dir = install_path / "scripts"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for filename in BOOTSTRAP_FILES:
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

    # Download model_manifest.json from Assets repo (HF primary, ModelScope fallback)
    _provision_bundles_manifest(dest_dir, log)

    # Download tools_manifest.json for wheel checksum verification
    _provision_tools_manifest(dest_dir, log)

    log.item(f"{copied} config file(s) provisioned.")


# Manifest URLs — the JSON lives in the Assets repo, not the installer.
_BUNDLES_MANIFEST_URLS = [
    "https://huggingface.co/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/main/model_manifest.json",
    "https://www.modelscope.ai/datasets/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/master/model_manifest.json",
]

_TOOLS_MANIFEST_URLS = [
    "https://huggingface.co/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/main/tools_manifest.json",
    "https://www.modelscope.ai/datasets/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/master/tools_manifest.json",
]


def _provision_bundles_manifest(dest_dir: Path, log: InstallerLogger) -> None:
    """Download ``model_manifest.json`` from the Assets repo.

    Tries HuggingFace first, then ModelScope.  If both fail and a
    previously-downloaded copy already exists locally, it is kept
    (offline-safe fallback).

    Args:
        dest_dir: Target ``scripts/`` directory.
        log: Installer logger.
    """
    bundles_dst = dest_dir / "model_manifest.json"

    try:
        download_file(
            _BUNDLES_MANIFEST_URLS,
            bundles_dst,
            force=True,  # always fetch latest manifest
        )
        log.sub("  model_manifest.json: downloaded from Assets repo", style="success")
    except RuntimeError:
        if bundles_dst.exists():
            log.sub(
                "  model_manifest.json: remote fetch failed, using existing local copy",
                style="cyan",
            )
        else:
            log.warning("  model_manifest.json: could not be downloaded (no local copy)", level=2)


def _provision_tools_manifest(dest_dir: Path, log: InstallerLogger) -> None:
    """Download ``tools_manifest.json`` from the Assets repo.

    Same fallback strategy as :func:`_provision_bundles_manifest`:
    HuggingFace first, ModelScope second, offline-safe if local copy
    exists.

    Args:
        dest_dir: Target ``scripts/`` directory.
        log: Installer logger.
    """
    tools_dst = dest_dir / "tools_manifest.json"

    try:
        download_file(
            _TOOLS_MANIFEST_URLS,
            tools_dst,
            force=True,
        )
        log.sub("  tools_manifest.json: downloaded from Assets repo", style="success")
    except RuntimeError:
        if tools_dst.exists():
            log.sub(
                "  tools_manifest.json: remote fetch failed, using existing local copy",
                style="cyan",
            )
        else:
            log.warning("  tools_manifest.json: could not be downloaded (no local copy)", level=2)


def load_tools_manifest(install_path: Path) -> dict:
    """Load ``tools_manifest.json`` from the install scripts directory.

    Returns the parsed JSON as a dict, or an empty dict if the file
    is not found or unparseable.

    Args:
        install_path: Root installation directory.

    Returns:
        Parsed manifest dict (or empty dict on failure).
    """
    import json

    manifest_path = install_path / "scripts" / "tools_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def lookup_wheel_checksum(
    manifest: dict,
    wheel_url: str,
) -> str | None:
    """Look up the SHA-256 checksum for a wheel from the tools manifest.

    Searches through all entries in the ``whl`` section for a matching
    filename.  Compares the path suffix (everything after the last
    ``whl/`` segment) to handle per-architecture subdirectories
    (e.g. ``whl/sm89/sageattention-2.2.0-cp313-cp313-linux_x86_64.whl``).

    Falls back to basename-only comparison for backwards compatibility
    with manifests that don't use subdirectories.

    Args:
        manifest: Parsed ``tools_manifest.json`` dict.
        wheel_url: Full URL of the wheel to look up.

    Returns:
        SHA-256 hex digest string, or ``None`` if not found.
    """
    if not manifest:
        return None

    # Extract the path after "whl/" from the URL for comparison
    # e.g. "https://...Assets/resolve/main/whl/sm89/sageattention-2.2.0-cp313-...whl"
    #   → "sm89/sageattention-2.2.0-cp313-...whl"
    url_whl_path = ""
    if "/whl/" in wheel_url:
        url_whl_path = wheel_url.split("/whl/", 1)[-1]

    url_basename = wheel_url.rsplit("/", 1)[-1] if "/" in wheel_url else wheel_url

    whl_section = manifest.get("whl", {})
    for _pkg_name, pkg_data in whl_section.items():
        if not isinstance(pkg_data, dict):
            continue
        files = pkg_data.get("files", {})
        for _key, file_info in files.items():
            if not isinstance(file_info, dict):
                continue
            manifest_filename = file_info.get("filename", "")

            # Prefer full path match (handles per-arch subdirectories)
            if url_whl_path and manifest_filename:
                # manifest stores e.g. "whl/sm89/sageattention-2.2.0-..."
                manifest_whl_path = manifest_filename.split("whl/", 1)[-1] if "whl/" in manifest_filename else ""
                if manifest_whl_path and manifest_whl_path == url_whl_path:
                    return file_info.get("sha256")

            # Fallback: basename comparison (backwards compat)
            manifest_basename = manifest_filename.rsplit("/", 1)[-1]
            if manifest_basename == url_basename:
                return file_info.get("sha256")

    return None


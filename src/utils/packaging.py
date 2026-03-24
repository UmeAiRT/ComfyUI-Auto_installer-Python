"""
Centralized UV package management.

All Python package installations go through :func:`uv_install`.
No pip fallback — ``uv`` is required (the bootstrap downloads it).

Replaces all raw ``python -m pip install`` calls across the codebase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.utils.commands import run_and_log
from src.utils.logging import get_logger

if TYPE_CHECKING:
    import subprocess
    from pathlib import Path

    from src.utils.logging import InstallerLogger


class UvNotFoundError(RuntimeError):
    """Raised when ``uv`` is not available on the system."""


def find_uv(install_path: Path | None = None) -> str | None:
    """Find the ``uv`` executable.

    Checks the local ``scripts/uv/`` directory first (where the
    bootstrap installs it), then falls back to the system PATH.

    Args:
        install_path: Root install directory (e.g. ``~/ComfyUI``).
            If provided, checks ``install_path/scripts/uv/uv[.exe]``.

    Returns:
        Absolute path to ``uv``, or ``None`` if not found.
    """
    import shutil
    import sys

    # 1. Check local install path
    if install_path is not None:
        uv_dir = install_path / "scripts" / "uv"
        if sys.platform == "win32":
            local_uv = uv_dir / "uv.exe"
        else:
            local_uv = uv_dir / "uv"
        if local_uv.is_file():
            return str(local_uv)

    # 2. Fall back to system PATH
    path = shutil.which("uv")
    return path


def _ensure_uv(install_path: Path | None = None) -> str:
    """Verify that ``uv`` exists and return its path.

    Raises:
        UvNotFoundError: If ``uv`` cannot be found.
    """
    path = find_uv(install_path)
    if path is None:
        raise UvNotFoundError(
            "uv is not installed or not in PATH. "
            "The bootstrap (Install.bat/Install.sh) should have installed it."
        )
    return path


def uv_install(
    python_exe: Path,
    packages: list[str] | None = None,
    *,
    index_url: str | None = None,
    requirements: Path | None = None,
    upgrade: bool = False,
    no_build_isolation: bool = False,
    no_deps: bool = False,
    editable: Path | None = None,
    ignore_errors: bool = False,
    timeout: int = 600,
    log: InstallerLogger | None = None,
) -> subprocess.CompletedProcess[str]:
    """Install Python packages via ``uv pip install``.

    Builds the full ``uv pip install`` command and delegates to
    :func:`~src.utils.commands.run_and_log`.

    Args:
        python_exe: Path to the target venv Python executable.
            Passed as ``--python`` so the venv does not need to be
            activated.
        packages: Package specifiers to install (e.g. ``["torch==2.10"]``).
        index_url: PyPI index URL override (``--index-url``).
        requirements: Path to a ``requirements.txt`` file (``-r``).
        upgrade: If ``True``, add ``--upgrade``.
        no_build_isolation: If ``True``, add ``--no-build-isolation``.
        no_deps: If ``True``, add ``--no-deps``.
        editable: Path to install in editable mode (``-e``).
        ignore_errors: Forwarded to :func:`run_and_log`.
        timeout: Command timeout in seconds.

    Returns:
        The completed process result.

    Raises:
        UvNotFoundError: If ``uv`` is not available.
        CommandError: If the command fails and *ignore_errors* is False.
    """
    uv_path = _ensure_uv()
    if log is None:
        log = get_logger()

    args: list[str] = ["pip", "install", "--python", str(python_exe)]

    if upgrade:
        args.append("--upgrade")

    if index_url:
        args.extend(["--index-url", index_url])

    if no_build_isolation:
        args.append("--no-build-isolation")

    if no_deps:
        args.append("--no-deps")

    if requirements:
        args.extend(["-r", str(requirements)])

    if editable:
        args.extend(["-e", str(editable)])

    if packages:
        args.extend(packages)

    log.info(f"uv {' '.join(args)}")

    return run_and_log(
        uv_path,
        args,
        ignore_errors=ignore_errors,
        timeout=timeout,
    )

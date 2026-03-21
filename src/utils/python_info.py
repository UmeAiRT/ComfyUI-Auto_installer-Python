"""
Python version detection for virtual environments.

Extracts the Python major.minor version from a venv's ``python`` executable
without importing anything from the venv itself — just runs a one-liner and
parses stdout.

Raises :class:`RuntimeError` on failure instead of falling back to a
hard-coded default (which could silently install wrong wheels).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def detect_venv_python_version(python_exe: Path) -> tuple[int, int]:
    """Detect Python version from a venv executable.

    Runs ``python -c "import sys; print(sys.version_info.major, sys.version_info.minor)"``
    and parses the output.

    Args:
        python_exe: Path to the venv Python executable.

    Returns:
        ``(major, minor)`` tuple, e.g. ``(3, 13)``.

    Raises:
        RuntimeError: If the subprocess fails or returns unexpected output.
    """
    try:
        result = subprocess.run(  # returncode checked below
            [str(python_exe), "-c",
             "import sys; print(sys.version_info.major, sys.version_info.minor)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        raise RuntimeError(
            f"Failed to detect Python version from {python_exe}: {exc}"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Python version detection failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    parts = result.stdout.strip().split()
    if len(parts) != 2:
        raise RuntimeError(
            f"Unexpected version output from {python_exe}: {result.stdout.strip()!r}"
        )

    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise RuntimeError(
            f"Could not parse version numbers from {result.stdout.strip()!r}"
        ) from exc

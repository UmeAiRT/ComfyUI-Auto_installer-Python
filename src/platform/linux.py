"""
Linux-specific platform implementation.

Handles symlinks, Python detection, and admin checks on Linux systems.
Long path support is a no-op (Linux has no 260-char limit).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from src.platform.base import Platform
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.utils.logging import InstallerLogger


class LinuxPlatform(Platform):
    """Linux platform implementation."""

    @property
    def name(self) -> str:
        return "linux"

    def is_admin(self) -> bool:
        """Check if running as root."""
        return os.getuid() == 0

    def enable_long_paths(self, log: InstallerLogger | None = None) -> bool:
        """No-op on Linux — long paths are always supported."""
        if log is None:
            log = get_logger()
        log.sub("Long path support: native (no action needed).", style="success")
        return True

    def detect_python(self, version: str = "3.13", log: InstallerLogger | None = None) -> Path | None:
        """
        Detect a specific Python version on Linux.

        Checks: python3.13, python3, python in PATH.

        Args:
            version: The version to look for (e.g. "3.13").
            log: Optional logger instance.

        Returns:
            Path to python executable, or None.
        """
        if log is None:
            log = get_logger()

        # 1. Try version-specific binary (e.g. python3.13)
        versioned = shutil.which(f"python{version}")
        if versioned:
            log.sub(f"Python {version} found: {versioned}", style="success")
            return Path(versioned)

        # 2. Try python3 and check version
        for candidate_name in ("python3", "python"):
            candidate = shutil.which(candidate_name)
            if candidate:
                try:
                    result = subprocess.run(
                        [candidate, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0 and f"Python {version}" in result.stdout:
                        log.sub(f"Python {version} found: {candidate}", style="success")
                        return Path(candidate)
                except (subprocess.TimeoutExpired, OSError):
                    pass

        return None

    def get_app_data_dir(self) -> Path:
        """Get the XDG data directory (~/.local/share)."""
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            return Path(xdg)
        return Path.home() / ".local" / "share"

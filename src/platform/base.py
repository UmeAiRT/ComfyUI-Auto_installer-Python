"""
Abstract base class for platform-specific operations.

This abstraction layer enables cross-platform support by defining
a common interface for operations that differ between Windows, Linux, and macOS.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from pathlib import Path


class Platform(ABC):
    """Abstract base class for platform-specific operations."""

    @abstractmethod
    def create_link(self, source: Path, target: Path) -> None:
        """
        Create a directory link (junction on Windows, symlink on Unix).

        Args:
            source: The link path to create (inside ComfyUI).
            target: The target path (external folder).
        """
        ...

    @abstractmethod
    def is_admin(self) -> bool:
        """Check if the current process has administrator/root privileges."""
        ...

    @abstractmethod
    def enable_long_paths(self) -> bool:
        """
        Enable support for long file paths (>260 chars).

        Returns:
            True if long paths were enabled or already enabled.
        """
        ...

    @abstractmethod
    def detect_python(self, version: str = "3.13") -> Path | None:
        """
        Detect a specific Python version on the system.

        Args:
            version: The Python version to look for (e.g. "3.13").

        Returns:
            Path to the Python executable, or None if not found.
        """
        ...

    @abstractmethod
    def get_app_data_dir(self) -> Path:
        """Get the platform-specific application data directory."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform name (e.g. 'windows', 'linux', 'macos')."""
        ...

    def is_link(self, path: Path) -> bool:
        """Check if a path is a link (junction or symlink)."""
        return path.is_symlink() or (path.exists() and path.is_junction())


def get_platform() -> Platform:
    """
    Detect and return the appropriate Platform implementation.

    Returns:
        A Platform instance for the current OS.

    Raises:
        NotImplementedError: If the current OS is not supported.
    """
    if sys.platform == "win32":
        from src.platform.windows import WindowsPlatform

        return WindowsPlatform()
    elif sys.platform == "linux":
        # Future: from src.platform.linux import LinuxPlatform
        raise NotImplementedError("Linux support is planned but not yet implemented.")
    elif sys.platform == "darwin":
        # Future: from src.platform.macos import MacOSPlatform
        raise NotImplementedError("macOS support is planned but not yet implemented.")
    else:
        raise NotImplementedError(f"Platform '{sys.platform}' is not supported.")

"""
Windows-specific platform implementation.

Handles NTFS junctions, registry operations, admin privilege checks,
and Python detection on Windows systems.
"""

from __future__ import annotations

import os
import shutil
import subprocess

try:
    import winreg
except ImportError:
    winreg = None  # Only used on Windows, but caught for cross-platform CI tests
from pathlib import Path
from typing import TYPE_CHECKING

from src.platform.base import Platform
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.utils.logging import InstallerLogger


class WindowsPlatform(Platform):
    """Windows platform implementation."""

    @property
    def name(self) -> str:
        return "windows"

    def create_link(self, source: Path, target: Path, log: InstallerLogger | None = None) -> None:
        """
        Create an NTFS junction (directory link).

        This replaces the PowerShell: cmd /c mklink /J "source" "target"

        Args:
            source: The junction path to create (inside ComfyUI).
            target: The target directory (external folder).
            log: Optional logger instance.

        Raises:
            RuntimeError: If junction creation fails.
        """
        if log is None:
            log = get_logger()

        if source.exists():
            if self.is_link(source):
                log.info(f"Junction already exists: {source.name}")
                return
            else:
                raise RuntimeError(
                    f"Cannot create junction: '{source}' already exists and is not a junction. "
                    "Please remove it manually."
                )

        # Use mklink /J for NTFS junctions (no admin required)
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(source), str(target)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create junction '{source}' → '{target}': {result.stderr}")

        # Verify junction was created
        if not source.exists():
            raise RuntimeError(f"Junction creation returned success but '{source}' does not exist.")

        log.sub(f"Linked {source.name} → {target.name} (External)", style="cyan")

    def is_admin(self) -> bool:
        """Check if running with Administrator privileges."""
        try:
            import ctypes

            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except (AttributeError, OSError):
            return False

    def enable_long_paths(self, log: InstallerLogger | None = None) -> bool:
        """
        Enable Windows long path support via registry.

        Sets HKLM\\SYSTEM\\CurrentControlSet\\Control\\FileSystem\\LongPathsEnabled = 1.

        Returns:
            True if enabled or already enabled, False on failure.
        """
        if log is None:
            log = get_logger()

        reg_path = r"SYSTEM\CurrentControlSet\Control\FileSystem"
        reg_key = "LongPathsEnabled"

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, reg_key)
                if value == 1:
                    log.sub("Long path support already enabled.", style="success")
                    return True
        except OSError:
            pass  # Key doesn't exist yet

        if not self.is_admin():
            log.warning("Long path support is not enabled and requires admin rights.", level=2)
            log.item("Run this command in an elevated PowerShell to enable it:")
            log.item(
                '  Set-ItemProperty -Path "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem" '
                '-Name "LongPathsEnabled" -Value 1 -Type DWord'
            )
            log.item("Then restart this installer.")
            return False

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, reg_key, 0, winreg.REG_DWORD, 1)
            log.sub("Long path support enabled.", style="success")
            return True
        except OSError as e:
            log.error(f"Failed to enable long paths: {e}", level=2)
            return False

    def detect_python(self, version: str = "3.13", log: InstallerLogger | None = None) -> Path | None:
        """
        Detect a specific Python version on Windows.

        Checks: py launcher (-3.13), python in PATH, common install paths.

        Args:
            version: The version to look for (e.g. "3.13").
            log: Optional logger instance.

        Returns:
            Path to python.exe, or None.
        """
        if log is None:
            log = get_logger()

        # 1. Try Python Launcher (py -3.13)
        py_launcher = shutil.which("py")
        if py_launcher:
            try:
                result = subprocess.run(
                    ["py", f"-{version}", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and f"Python {version}" in result.stdout:
                    log.sub(f"Python Launcher detected with Python {version}.", style="success")
                    # Return the actual python.exe path from the launcher
                    which_result = subprocess.run(
                        ["py", f"-{version}", "-c", "import sys; print(sys.executable)"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if which_result.returncode == 0:
                        return Path(which_result.stdout.strip())
            except (subprocess.TimeoutExpired, OSError):
                pass

        # 2. Try system PATH
        python_exe = shutil.which("python")
        if python_exe:
            try:
                result = subprocess.run(
                    [python_exe, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and f"Python {version}" in result.stdout:
                    log.sub(f"System Python {version} detected.", style="success")
                    return Path(python_exe)
            except (subprocess.TimeoutExpired, OSError):
                pass

        # 3. Check common install paths
        version_nodot = version.replace(".", "")
        common_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / f"Programs/Python/Python{version_nodot}/python.exe",
            Path(f"C:/Python{version_nodot}/python.exe"),
            Path(f"C:/Program Files/Python{version_nodot}/python.exe"),
        ]

        for path in common_paths:
            if path.exists():
                log.sub(f"Python found at: {path}", style="success")
                return path

        return None

    def get_app_data_dir(self) -> Path:
        """Get the Windows LOCALAPPDATA directory."""
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))

"""
Safe subprocess execution with logging.

Replaces the PowerShell Invoke-AndLog function from UmeAiRTUtils.psm1.
Uses subprocess.run() with explicit argument lists — no shell injection possible.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from src.utils.logging import get_logger


class CommandError(Exception):
    """Raised when an external command fails."""

    def __init__(self, command: str, return_code: int, stderr: str = "") -> None:
        self.command = command
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(f"Command failed (code {return_code}): {command}")


def run_and_log(
    command: str | Path,
    args: list[str] | None = None,
    *,
    cwd: Path | None = None,
    ignore_errors: bool = False,
    timeout: int = 600,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """
    Execute an external command, logging both the command and its output.

    This is a secure replacement for the PowerShell Invoke-AndLog function.
    It uses subprocess.run() with an explicit argument list, preventing
    any shell injection attacks.

    Args:
        command: Path to the executable.
        args: List of arguments (NOT a single string — safe by design).
        cwd: Working directory for the command.
        ignore_errors: If True, don't raise on non-zero exit codes.
        timeout: Command timeout in seconds (default: 10 minutes).
        env: Optional environment variables to set.

    Returns:
        The completed process result.

    Raises:
        CommandError: If command fails and ignore_errors is False.
    """
    log = get_logger()

    full_args = [str(command)] + (args or [])
    cmd_display = " ".join(full_args)

    log.info(f"Executing: {cmd_display}")

    try:
        import os

        run_env = None
        if env:
            run_env = {**os.environ, **env}

        result = subprocess.run(
            full_args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env=run_env,
        )

        # Log output to file
        if result.stdout:
            for line in result.stdout.strip().split("\n")[:50]:  # Cap log output
                log.info(line)

        if result.returncode != 0 and not ignore_errors:
            log.error(f"Command failed with code {result.returncode}.")
            log.error(f"Command: {cmd_display}")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[:20]:
                    log.error(line, level=3)
            raise CommandError(cmd_display, result.returncode, result.stderr)

        return result

    except subprocess.TimeoutExpired as e:
        msg = f"Command timed out after {timeout}s: {cmd_display}"
        log.error(msg)
        raise CommandError(cmd_display, -1, "timeout") from e

    except FileNotFoundError as e:
        msg = f"Command not found: {command}"
        log.error(msg)
        raise CommandError(str(command), -1, "not found") from e


def check_command_exists(command: str) -> bool:
    """
    Check if a command is available in the system PATH.

    Args:
        command: The executable name to look for.

    Returns:
        True if the command exists and is executable.
    """
    import shutil

    return shutil.which(command) is not None


def get_command_version(command: str, version_flag: str = "--version") -> str | None:
    """
    Get the version string of a command.

    Args:
        command: The executable to query.
        version_flag: The flag to get version (default: --version).

    Returns:
        The version output string, or None if command fails.
    """
    try:
        result = subprocess.run(
            [command, version_flag],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip() or result.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None

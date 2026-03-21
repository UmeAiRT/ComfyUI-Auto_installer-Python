"""
Structured logging with Rich.

Replaces the PowerShell Write-Log function from UmeAiRTUtils.psm1.
Provides dual output: colored console (via Rich) + timestamped log file.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rich.console import Console
from rich.theme import Theme

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Custom Rich theme matching the PowerShell color scheme
# ---------------------------------------------------------------------------
_THEME = Theme(
    {
        "step": "bold yellow",
        "success": "bold green",
        "warning": "bold yellow",
        "error": "bold red",
        "info": "dim white",
        "debug": "dim cyan",
        "cyan": "bold cyan",
    }
)

console = Console(theme=_THEME)


class InstallerLogger:
    """
    Structured logger for the installer.

    Replaces the PowerShell Write-Log system with levels:
        -2: Raw output (no prefix)
         0: Step header (yellow, with separators and step counter)
         1: Main item ("  - ")
         2: Sub-item ("    -> ")
         3: Info/Debug ("      [INFO] ")
    """

    def __init__(
        self,
        log_file: Path | None = None,
        total_steps: int = 0,
        verbose: bool = False,
    ) -> None:
        self.total_steps = total_steps
        self.current_step = 0
        self.verbose = verbose
        self._log_file = log_file
        self._file_logger: logging.Logger | None = None

        if log_file:
            self._setup_file_logger(log_file)

    def _setup_file_logger(self, log_file: Path) -> None:
        """Configure the file-based logger."""
        log_file.parent.mkdir(parents=True, exist_ok=True)

        self._file_logger = logging.getLogger("comfyui_installer")
        self._file_logger.setLevel(logging.DEBUG)

        # Remove existing handlers to avoid duplicates on re-init
        for handler in list(self._file_logger.handlers):
            handler.close()
            self._file_logger.removeHandler(handler)

        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        self._file_logger.addHandler(handler)

    @property
    def log_file(self) -> Path | None:
        return self._log_file

    @log_file.setter
    def log_file(self, path: Path) -> None:
        self._log_file = path
        self._setup_file_logger(path)

    def log(self, message: str, *, level: int = 1, style: str = "") -> None:
        """
        Log a message with the given level.

        Args:
            message: The message to display.
            level: Indentation/formatting level (-2, 0, 1, 2, 3).
            style: Rich style override (e.g. "success", "error", "warning").
        """
        if level == -2:
            # Raw output — no prefix
            console_msg = message
            file_msg = message
        elif level == 0:
            # Step header
            self.current_step += 1
            step_str = f"[Step {self.current_step}/{self.total_steps}]"
            inner = f"| {step_str} {message} |"
            separator = "=" * len(inner)
            console_msg = f"\n{separator}\n{inner}\n{separator}"
            file_msg = f"{step_str} {message}"
            style = style or "step"
        elif level == 1:
            console_msg = f"  - {message}"
            file_msg = f"- {message}"
        elif level == 2:
            console_msg = f"    -> {message}"
            file_msg = f"-> {message}"
        elif level == 3:
            console_msg = f"      [INFO] {message}"
            file_msg = f"[INFO] {message}"
            style = style or "info"
            # In non-verbose mode, skip console output for INFO
            if not self.verbose:
                if self._file_logger:
                    self._file_logger.info(file_msg)
                return
        else:
            console_msg = message
            file_msg = message

        # Console output
        if style:
            console.print(console_msg, style=style)
        else:
            console.print(console_msg)

        # File output
        if self._file_logger:
            self._file_logger.info(file_msg)

    # -----------------------------------------------------------------------
    # Convenience shortcuts
    # -----------------------------------------------------------------------
    def step(self, message: str) -> None:
        """Log a step header (level 0)."""
        self.log(message, level=0)

    def item(self, message: str, *, style: str = "") -> None:
        """Log a main item (level 1)."""
        self.log(message, level=1, style=style)

    def sub(self, message: str, *, style: str = "") -> None:
        """Log a sub-item (level 2)."""
        self.log(message, level=2, style=style)

    def info(self, message: str) -> None:
        """Log an info/debug message (level 3)."""
        self.log(message, level=3)

    def skip_step(self, message: str) -> None:
        """Record a skipped step — adjusts total so the counter stays accurate.

        Use this instead of silently returning when a step is conditionally
        skipped.  The total is decremented so that subsequent ``step()``
        calls still display ``[Step N/M]`` with a correct *M*.
        """
        if self.total_steps > 0:
            self.total_steps -= 1
        self.log(f"⏭  {message} (skipped)", level=1, style="info")

    def success(self, message: str, *, level: int = 1) -> None:
        """Log a success message."""
        self.log(message, level=level, style="success")

    def warning(self, message: str, *, level: int = 1) -> None:
        """Log a warning message."""
        self.log(message, level=level, style="warning")

    def error(self, message: str, *, level: int = 1) -> None:
        """Log an error message."""
        self.log(message, level=level, style="error")

    def banner(self, title: str, subtitle: str = "", version: str = "") -> None:
        """Display a startup banner."""
        sep = "─" * 70
        console.print(f"\n{sep}", style="cyan")
        if title:
            console.print(f"  {title}", style="bold cyan")
        if subtitle:
            console.print(f"  {subtitle}", style="step")
        if version:
            console.print(f"  Version {version}", style="dim white")
        console.print(f"{sep}\n", style="cyan")


# ---------------------------------------------------------------------------
# Module-level singleton (convenience)
# ---------------------------------------------------------------------------
_default_logger: InstallerLogger | None = None


def setup_logger(
    log_file: Path | None = None,
    total_steps: int = 0,
    verbose: bool = False,
) -> InstallerLogger:
    """Create or reconfigure the default logger."""
    global _default_logger
    _default_logger = InstallerLogger(log_file=log_file, total_steps=total_steps, verbose=verbose)
    return _default_logger


def get_logger() -> InstallerLogger:
    """Get the default logger, creating one if needed."""
    global _default_logger
    if _default_logger is None:
        _default_logger = InstallerLogger()
    return _default_logger

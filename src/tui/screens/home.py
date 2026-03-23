"""
Home Screen — Main menu for UmeAiRT ComfyUI TUI.

Shows the logo, system info bar, and action buttons.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from src.settings import UserSettings

# ── ASCII Art Logo ──────────────────────────────────────────────────
LOGO = r"""
 ╦ ╦┌┬┐┌─┐╔═╗┬╦═╗╔╦╗
 ║ ║│││├┤ ╠═╣│╠╦╝ ║
 ╚═╝┴ ┴└─┘╩ ╩┴╩╚═ ╩
  ── ComfyUI ──
"""


def _get_system_summary() -> str:
    """Build a one-line system overview."""
    parts = [f"Python {sys.version_info.major}.{sys.version_info.minor}"]

    try:
        from src.utils.gpu import get_gpu_vram_info
        gpu = get_gpu_vram_info()
        if gpu:
            parts.append(f"{gpu.name} ({gpu.vram_gib}GB)")
    except Exception:
        pass

    try:
        import torch
        parts.append(f"PyTorch {torch.__version__}")
    except ImportError:
        pass

    return "  │  ".join(parts)


class HomeScreen(Screen):
    """Main menu screen."""

    def __init__(
        self,
        install_path: Path,
        settings: UserSettings,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.install_path = install_path
        self.user_settings = settings

    def compose(self) -> ComposeResult:
        """Build the home screen layout."""
        yield Header(show_clock=True)
        with Vertical(id="home-container"):
            yield Static(LOGO, id="logo-panel")
            yield Static(_get_system_summary(), id="system-info-bar")

            with Center(id="menu-container"):
                yield Button(
                    "🚀  Launch ComfyUI",
                    id="btn-launch",
                    classes="menu-button -primary",
                )
                yield Button(
                    "⬇️   Download Models",
                    id="btn-download",
                    classes="menu-button",
                )
                yield Button(
                    "🔄  Update ComfyUI + Nodes",
                    id="btn-update",
                    classes="menu-button",
                )
                yield Button(
                    "🔧  Install (first-time setup)",
                    id="btn-install",
                    classes="menu-button",
                )
                yield Button(
                    "🔍  Scan Models (security)",
                    id="btn-scan",
                    classes="menu-button",
                )
                yield Button(
                    "ℹ️   System Info",
                    id="btn-info",
                    classes="menu-button",
                )
                yield Button(
                    "⚙️   Settings",
                    id="btn-settings",
                    classes="menu-button",
                )
                yield Button(
                    "❌  Exit",
                    id="btn-exit",
                    classes="menu-button -danger",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu button clicks."""
        button_id = event.button.id

        if button_id == "btn-exit":
            self.app.exit()

        elif button_id == "btn-launch":
            from src.tui.screens.launch import LaunchScreen
            self.app.push_screen(LaunchScreen(self.install_path, self.user_settings))

        elif button_id == "btn-info":
            from src.tui.screens.info import InfoScreen
            self.app.push_screen(InfoScreen())

        elif button_id == "btn-settings":
            from src.tui.screens.settings import SettingsScreen
            self.app.push_screen(
                SettingsScreen(self.install_path, self.user_settings)
            )

        elif button_id == "btn-download":
            from src.tui.screens.download import DownloadScreen
            self.app.push_screen(DownloadScreen(self.install_path))

        elif button_id == "btn-update":
            self._run_cli_command("update")

        elif button_id == "btn-install":
            self._run_cli_command("install")

        elif button_id == "btn-scan":
            self._run_cli_command("scan-models")

    def _run_cli_command(self, command: str) -> None:
        """Exit TUI and run a CLI command in the terminal."""
        self.app.exit(result=command)

"""
UmeAiRT ComfyUI — Main TUI Application.

Entry point for the interactive terminal interface.
Uses Textual framework with a custom theme for AI artists.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding

from src import __version__
from src.settings import UserSettings


class UmeAiRTApp(App):
    """Main TUI application for UmeAiRT ComfyUI."""

    TITLE = "UmeAiRT ComfyUI"
    SUB_TITLE = f"v{__version__}"
    CSS_PATH = "theme.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "back", "Back", show=True),
        Binding("f2", "settings", "Settings", show=True),
    ]

    def __init__(self, install_path: Path | None = None) -> None:
        super().__init__()
        self.install_path = install_path or Path.cwd()
        self.user_settings = UserSettings.load(self.install_path)

    def on_mount(self) -> None:
        """Push the home screen on startup."""
        from src.tui.screens.home import HomeScreen
        self.push_screen(HomeScreen(self.install_path, self.user_settings))

    def action_back(self) -> None:
        """Handle back/escape action."""
        if len(self.screen_stack) > 1:
            self.pop_screen()

    def action_settings(self) -> None:
        """Open settings screen."""
        from src.tui.screens.settings import SettingsScreen
        self.push_screen(SettingsScreen(self.install_path, self.user_settings))


def run_tui(install_path: Path | None = None) -> None:
    """Launch the TUI application."""
    app = UmeAiRTApp(install_path=install_path)
    return app.run()

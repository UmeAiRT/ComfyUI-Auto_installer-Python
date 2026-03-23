"""
Settings Screen — Configure user preferences.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Select, Static, Switch

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult

    from src.settings import UserSettings


class SettingsScreen(Screen):
    """User settings configuration."""

    BINDINGS = [("escape", "app.back", "Back")]

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
        """Build the settings form."""
        s = self.user_settings

        with Vertical(id="settings-container"):
            yield Static("[b]⚙️  Settings[/b]\n", id="settings-panel")

            # Listen address
            yield Static("[b]Network Listen Address[/b]")
            yield Select(
                [
                    ("127.0.0.1  (local only)", "127.0.0.1"),
                    ("0.0.0.0  (LAN / cloud)", "0.0.0.0"),
                ],
                value=s.listen_address,
                id="sel-listen",
            )

            # VRAM mode
            yield Static("\n[b]VRAM Mode[/b]")
            yield Select(
                [
                    ("Auto (recommended)", "auto"),
                    ("Normal", "normal"),
                    ("Low VRAM", "low"),
                    ("High VRAM", "high"),
                ],
                value=s.vram_mode,
                id="sel-vram",
            )

            # Toggles
            yield Static("\n[b]SageAttention[/b]")
            yield Switch(value=s.use_sage_attention, id="sw-sage")

            yield Static("[b]Auto-launch browser[/b]")
            yield Switch(value=s.auto_launch_browser, id="sw-browser")

            yield Static("")
            with Center():
                yield Button("💾  Save", id="btn-save", variant="success")
                yield Button("← Back", id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-save":
            self._save_settings()
            self.app.pop_screen()

    def _save_settings(self) -> None:
        """Collect values from widgets and save."""
        s = self.user_settings

        listen_sel = self.query_one("#sel-listen", Select)
        if listen_sel.value is not Select.BLANK:
            s.listen_address = str(listen_sel.value)

        vram_sel = self.query_one("#sel-vram", Select)
        if vram_sel.value is not Select.BLANK:
            s.vram_mode = str(vram_sel.value)

        s.use_sage_attention = self.query_one("#sw-sage", Switch).value
        s.auto_launch_browser = self.query_one("#sw-browser", Switch).value

        s.save(self.install_path)
        self.notify("Settings saved ✓", severity="information")

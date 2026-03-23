"""
Home Screen — Main menu for UmeAiRT ComfyUI TUI.

Shows the logo, system info bar, and action buttons.
Supports mouse clicks, Tab navigation, and number key shortcuts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.containers import Center, VerticalScroll
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

# Map button IDs to their index for keyboard focus
MENU_BUTTONS = [
    "btn-launch",
    "btn-download",
    "btn-update",
    "btn-install",
    "btn-scan",
    "btn-info",
    "btn-settings",
    "btn-exit",
]


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

    BINDINGS = [
        Binding("1", "menu_1", "Launch", show=False),
        Binding("2", "menu_2", "Download", show=False),
        Binding("3", "menu_3", "Update", show=False),
        Binding("4", "menu_4", "Install", show=False),
        Binding("5", "menu_5", "Scan", show=False),
        Binding("6", "menu_6", "Info", show=False),
        Binding("7", "menu_7", "Settings", show=False),
        Binding("8", "menu_8", "Exit", show=False),
        Binding("up,k", "focus_previous", "Up", show=False),
        Binding("down,j", "focus_next", "Down", show=False),
        Binding("enter", "press_focused", "Select", show=False),
    ]

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
        with VerticalScroll(id="home-container"):
            yield Static(LOGO, id="logo-panel")
            yield Static(_get_system_summary(), id="system-info-bar")

            with Center(id="menu-container"):
                yield Button(
                    "1 │ 🚀  Launch ComfyUI",
                    id="btn-launch",
                    classes="menu-button -primary",
                )
                yield Button(
                    "2 │ ⬇️   Download Models",
                    id="btn-download",
                    classes="menu-button",
                )
                yield Button(
                    "3 │ 🔄  Update ComfyUI + Nodes",
                    id="btn-update",
                    classes="menu-button",
                )
                yield Button(
                    "4 │ 🔧  Install (first-time setup)",
                    id="btn-install",
                    classes="menu-button",
                )
                yield Button(
                    "5 │ 🔍  Scan Models (security)",
                    id="btn-scan",
                    classes="menu-button",
                )
                yield Button(
                    "6 │ ℹ️   System Info",
                    id="btn-info",
                    classes="menu-button",
                )
                yield Button(
                    "7 │ ⚙️   Settings",
                    id="btn-settings",
                    classes="menu-button",
                )
                yield Button(
                    "8 │ ❌  Exit",
                    id="btn-exit",
                    classes="menu-button -danger",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Focus the first button on mount."""
        self.query_one("#btn-launch", Button).focus()

    # ── Number key shortcuts ────────────────────────────────────────
    def _press_button(self, index: int) -> None:
        """Simulate pressing a button by index."""
        if 0 <= index < len(MENU_BUTTONS):
            btn = self.query_one(f"#{MENU_BUTTONS[index]}", Button)
            btn.press()

    def action_menu_1(self) -> None:
        self._press_button(0)

    def action_menu_2(self) -> None:
        self._press_button(1)

    def action_menu_3(self) -> None:
        self._press_button(2)

    def action_menu_4(self) -> None:
        self._press_button(3)

    def action_menu_5(self) -> None:
        self._press_button(4)

    def action_menu_6(self) -> None:
        self._press_button(5)

    def action_menu_7(self) -> None:
        self._press_button(6)

    def action_menu_8(self) -> None:
        self._press_button(7)

    # ── Arrow key navigation ────────────────────────────────────────
    def action_press_focused(self) -> None:
        """Press the currently focused button."""
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    # ── Button handlers ─────────────────────────────────────────────
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

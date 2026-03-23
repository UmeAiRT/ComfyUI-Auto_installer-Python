"""
Home Screen — Main menu for UmeAiRT ComfyUI TUI.

Shows the logo, system info bar, and action buttons.
Supports mouse clicks, Tab navigation, and number key shortcuts.
Detects whether ComfyUI is installed to adjust available actions.
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


def _get_system_summary(install_path: Path) -> str:
    """Build a one-line system overview, querying the ComfyUI venv if available."""
    parts = [f"Python {sys.version_info.major}.{sys.version_info.minor}"]

    try:
        from src.utils.gpu import get_gpu_vram_info
        gpu = get_gpu_vram_info()
        if gpu:
            parts.append(f"{gpu.name} ({gpu.vram_gib}GB)")
    except Exception:
        pass

    # Try to get PyTorch version from the ComfyUI venv
    torch_version = _get_venv_torch_version(install_path)
    if torch_version:
        parts.append(f"PyTorch {torch_version}")

    return "  │  ".join(parts)


def _get_venv_torch_version(install_path: Path) -> str | None:
    """Query the ComfyUI venv for its PyTorch version."""
    import subprocess

    # Venv is at install_path/scripts/venv/ (see environment.py)
    if sys.platform == "win32":
        venv_python = install_path / "scripts" / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = install_path / "scripts" / "venv" / "bin" / "python"

    if not venv_python.exists():
        return None

    try:
        result = subprocess.run(  # noqa: S603
            [str(venv_python), "-c", "import torch; print(torch.__version__)"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _is_comfyui_installed(install_path: Path) -> bool:
    """Check if ComfyUI is installed at the given path."""
    return (install_path / "ComfyUI" / "main.py").exists()


class HomeScreen(Screen):
    """Main menu screen."""

    # Buttons list is built dynamically in on_mount based on install state
    _menu_buttons: list[str] = []

    BINDINGS = [
        Binding("1", "menu_1", show=False),
        Binding("2", "menu_2", show=False),
        Binding("3", "menu_3", show=False),
        Binding("4", "menu_4", show=False),
        Binding("5", "menu_5", show=False),
        Binding("6", "menu_6", show=False),
        Binding("7", "menu_7", show=False),
        Binding("8", "menu_8", show=False),
        Binding("up", "move_up", show=False, priority=True),
        Binding("down", "move_down", show=False, priority=True),
        Binding("k", "move_up", show=False),
        Binding("j", "move_down", show=False),
        Binding("enter", "press_focused", show=False, priority=True),
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
        self.comfyui_installed = _is_comfyui_installed(install_path)

    def compose(self) -> ComposeResult:
        """Build the home screen layout."""
        yield Header(show_clock=True)
        with VerticalScroll(id="home-container"):
            yield Static(LOGO, id="logo-panel")

            if self.comfyui_installed:
                yield Static(_get_system_summary(self.install_path), id="system-info-bar")
            else:
                yield Static(
                    "[bold yellow]⚠ ComfyUI not detected[/] — Run Install first",
                    id="system-info-bar",
                )

            with Center(id="menu-container"):
                if self.comfyui_installed:
                    yield from self._compose_installed_menu()
                else:
                    yield from self._compose_fresh_menu()
        yield Footer()

    def _compose_installed_menu(self):
        """Menu when ComfyUI is already installed."""
        self._menu_buttons = [
            "btn-launch", "btn-download", "btn-update",
            "btn-reinstall", "btn-install",
            "btn-info", "btn-exit",
        ]
        yield Button("1 │ 🚀  Launch ComfyUI", id="btn-launch", classes="menu-button -primary")
        yield Button("2 │ ⬇️   Download Models", id="btn-download", classes="menu-button")
        yield Button("3 │ 🔄  Update ComfyUI + Nodes", id="btn-update", classes="menu-button")
        yield Button("4 │ ♻️   Reinstall (clean)", id="btn-reinstall", classes="menu-button")
        yield Button("5 │ 🔧  New Installation", id="btn-install", classes="menu-button")
        yield Button("6 │ ℹ️   System Info", id="btn-info", classes="menu-button")
        yield Button("7 │ ❌  Exit", id="btn-exit", classes="menu-button -danger")

    def _compose_fresh_menu(self):
        """Menu when ComfyUI is not yet installed."""
        self._menu_buttons = [
            "btn-install", "btn-info", "btn-exit",
        ]
        yield Button("1 │ 🔧  Install ComfyUI", id="btn-install", classes="menu-button -primary")
        yield Button("2 │ ℹ️   System Info", id="btn-info", classes="menu-button")
        yield Button("3 │ ❌  Exit", id="btn-exit", classes="menu-button -danger")

    def on_mount(self) -> None:
        """Focus the appropriate button on mount."""
        if self._menu_buttons:
            self.query_one(f"#{self._menu_buttons[0]}", Button).focus()

    # ── Number key shortcuts ────────────────────────────────────────
    def _press_button(self, index: int) -> None:
        """Simulate pressing a button by index."""
        if 0 <= index < len(self._menu_buttons):
            btn = self.query_one(f"#{self._menu_buttons[index]}", Button)
            if not btn.disabled:
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
    def _get_focused_index(self) -> int:
        """Return the index of the currently focused button, or -1."""
        focused = self.focused
        if isinstance(focused, Button) and focused.id in self._menu_buttons:
            return self._menu_buttons.index(focused.id)
        return -1

    def action_move_down(self) -> None:
        """Move focus to the next menu button."""
        idx = self._get_focused_index()
        next_idx = (idx + 1) % len(self._menu_buttons)
        self.query_one(f"#{self._menu_buttons[next_idx]}", Button).focus()

    def action_move_up(self) -> None:
        """Move focus to the previous menu button."""
        idx = self._get_focused_index()
        prev_idx = (idx - 1) % len(self._menu_buttons)
        self.query_one(f"#{self._menu_buttons[prev_idx]}", Button).focus()

    def action_press_focused(self) -> None:
        """Press the currently focused button."""
        focused = self.focused
        if isinstance(focused, Button) and not focused.disabled:
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
            self.app.push_screen(InfoScreen(self.install_path))

        elif button_id == "btn-download":
            from src.tui.screens.download import DownloadScreen
            self.app.push_screen(DownloadScreen(self.install_path))

        elif button_id == "btn-update":
            self._run_cli_command("update")

        elif button_id == "btn-install":
            from src.tui.screens.install import InstallScreen
            self.app.push_screen(InstallScreen(self.install_path, self.user_settings))

        elif button_id == "btn-reinstall":
            self._run_cli_command("install --reinstall")

    def _run_cli_command(self, command: str) -> None:
        """Exit TUI and run a CLI command in the terminal."""
        self.app.exit(result=command)

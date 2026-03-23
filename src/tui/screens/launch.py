"""
Launch Screen — Choose VRAM mode and start ComfyUI.

Recommends a mode based on detected GPU VRAM.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from src.settings import UserSettings


def _detect_vram() -> float | None:
    """Detect GPU VRAM in GiB."""
    try:
        from src.utils.gpu import get_gpu_vram_info
        gpu = get_gpu_vram_info()
        if gpu:
            return gpu.vram_gib
    except Exception:
        pass
    return None


def _recommend_mode(vram_gib: float | None) -> str:
    """Recommend a VRAM mode based on detected VRAM."""
    if vram_gib is None:
        return "normal"
    if vram_gib >= 12:
        return "high"
    if vram_gib >= 8:
        return "normal"
    return "low"


# Mode descriptions for the UI
MODES = {
    "high": {
        "label": "🚀  Performance",
        "desc": "Keep models in VRAM — fastest generation, needs 12GB+",
        "flag": "--highvram",
    },
    "normal": {
        "label": "⚡  Normal",
        "desc": "Smart memory management — good for 8-12GB",
        "flag": "(default)",
    },
    "low": {
        "label": "🐢  Low VRAM",
        "desc": "Offload to RAM aggressively — for 4-8GB GPUs",
        "flag": "--lowvram",
    },
}

MODE_BUTTONS = ["btn-mode-high", "btn-mode-normal", "btn-mode-low"]


class LaunchScreen(Screen):
    """Choose VRAM mode and launch ComfyUI."""

    BINDINGS = [
        Binding("escape", "app.back", "Back"),
        Binding("up", "move_up", show=False, priority=True),
        Binding("down", "move_down", show=False, priority=True),
        Binding("enter", "press_focused", show=False, priority=True),
        Binding("1", "select_1", show=False),
        Binding("2", "select_2", show=False),
        Binding("3", "select_3", show=False),
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
        self.vram_gib = _detect_vram()
        self.recommended = _recommend_mode(self.vram_gib)

    def compose(self) -> ComposeResult:
        """Build the launch screen."""
        yield Header(show_clock=True)
        with Vertical(id="launch-container"):
            # Title + VRAM info
            vram_str = f"{self.vram_gib:.0f} GB" if self.vram_gib else "unknown"
            with Center():
                yield Static(
                    f"🚀 [b]Launch ComfyUI[/b]\n\n"
                    f"[b]GPU VRAM:[/b] {vram_str}",
                    id="launch-title",
                )

            with Center():
                yield Static("\n[b]Choose VRAM mode:[/b]", id="launch-subtitle")

            with Center(id="launch-modes"):
                for mode_key in ("high", "normal", "low"):
                    mode = MODES[mode_key]
                    rec = "  ⭐ recommended" if mode_key == self.recommended else ""
                    classes = "mode-button"
                    if mode_key == self.recommended:
                        classes += " -primary"
                    yield Button(
                        f"{mode['label']}\n{mode['desc']}{rec}",
                        id=f"btn-mode-{mode_key}",
                        classes=classes,
                    )

            # SageAttention toggle info
            sage = "✅" if self.user_settings.use_sage_attention else "❌"
            with Center():
                yield Static(
                    f"\n[dim]SageAttention: {sage}  •  Listen: {self.user_settings.listen_address}  •  "
                    f"Change in Settings[/dim]",
                    id="launch-info",
                )

            with Center():
                yield Button("← Back", id="btn-back", classes="menu-button")
        yield Footer()

    def on_mount(self) -> None:
        """Focus the recommended mode button."""
        self.query_one(f"#btn-mode-{self.recommended}", Button).focus()

    # ── Navigation ──
    def _get_focused_index(self) -> int:
        focused = self.focused
        if isinstance(focused, Button) and focused.id in MODE_BUTTONS:
            return MODE_BUTTONS.index(focused.id)
        return -1

    def action_move_down(self) -> None:
        idx = self._get_focused_index()
        if idx >= 0:
            next_idx = min(idx + 1, len(MODE_BUTTONS) - 1)
            self.query_one(f"#{MODE_BUTTONS[next_idx]}", Button).focus()

    def action_move_up(self) -> None:
        idx = self._get_focused_index()
        if idx >= 0:
            prev_idx = max(idx - 1, 0)
            self.query_one(f"#{MODE_BUTTONS[prev_idx]}", Button).focus()

    def action_press_focused(self) -> None:
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_select_1(self) -> None:
        self.query_one("#btn-mode-high", Button).press()

    def action_select_2(self) -> None:
        self.query_one("#btn-mode-normal", Button).press()

    def action_select_3(self) -> None:
        self.query_one("#btn-mode-low", Button).press()

    # ── Button handlers ──
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle mode selection or back."""
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id and event.button.id.startswith("btn-mode-"):
            mode = event.button.id.replace("btn-mode-", "")
            self._launch_with_mode(mode)

    def _launch_with_mode(self, mode: str) -> None:
        """Save mode, build args, and launch ComfyUI."""
        # Update settings with chosen mode
        self.user_settings.vram_mode = mode
        self.user_settings.save(self.install_path)

        comfy_path = self.install_path / "ComfyUI"
        if not (comfy_path / "main.py").exists():
            self.app.bell()
            return

        # Find Python: venv first, then embedded, then system
        venv_python = self.install_path / "scripts" / "venv"
        if sys.platform == "win32":
            python_exe = venv_python / "Scripts" / "python.exe"
        else:
            python_exe = venv_python / "bin" / "python"

        if not python_exe.exists():
            embedded = self.install_path / "python_embeded" / "python.exe"
            python_exe = embedded if embedded.exists() else Path(sys.executable)

        args = [str(python_exe), "-s", str(comfy_path / "main.py")]

        # Standalone flag for portable builds
        if (self.install_path / "python_embeded").exists():
            args.append("--windows-standalone-build")

        args.extend(self.user_settings.build_comfyui_args())

        # Return launch info — cli.py will execute after TUI is fully closed
        self.app.exit(result={
            "action": "launch",
            "args": args,
            "cwd": str(self.install_path),
            "mode": mode,
        })

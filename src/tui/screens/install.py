"""
Install Screen — Configure and launch ComfyUI installation.

Offers choice of environment type and node tier before starting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Select, Static

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult

    from src.settings import UserSettings


class InstallScreen(Screen):
    """Installation configuration screen."""

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
        """Build the install configuration layout."""
        yield Header(show_clock=True)
        with Vertical(id="install-container"):
            with Center():
                yield Static(
                    "🔧 [b]Install ComfyUI[/b]",
                    id="install-title",
                )

            with Center(), Vertical(id="install-form"):
                yield Static("[b]Install Path[/b]")
                yield Input(
                    value=str(self.install_path),
                    placeholder="C:\\path\\to\\comfyui",
                    id="input-path",
                )

                yield Static("[b]Environment Type[/b]")
                yield Select(
                    [
                        ("venv  — Lightweight (recommended)", "venv"),
                        ("conda — Full Anaconda environment", "conda"),
                    ],
                    value="venv",
                    id="sel-env-type",
                )

                yield Static("[b]Custom Nodes Bundle[/b]")
                yield Select(
                    [
                        ("minimal  — ComfyUI Manager only", "minimal"),
                        ("umeairt  — UmeAiRT curated nodes", "umeairt"),
                        ("full     — All recommended nodes", "full"),
                    ],
                    value="full",
                    id="sel-node-tier",
                )

                yield Static("[b]GPU / CUDA[/b]")
                yield Select(
                    [
                        ("Auto-detect (recommended)", ""),
                        ("CUDA 13.0 (RTX 40xx+)", "cu130"),
                        ("CUDA 12.8 (RTX 30xx+)", "cu128"),
                        ("ROCm 7.1 (AMD Linux)", "rocm71"),
                        ("DirectML (AMD Windows)", "directml"),
                        ("CPU only", "cpu"),
                    ],
                    value="",
                    id="sel-cuda",
                )

                yield Static("")
                yield Button(
                    "🚀  Start Installation",
                    id="btn-start-install",
                    classes="menu-button -primary",
                )
                yield Button(
                    "← Back",
                    id="btn-back",
                    classes="menu-button",
                )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-start-install":
            self._start_install()

    def _start_install(self) -> None:
        """Build install command and exit TUI to run it."""
        path_input = self.query_one("#input-path", Input)
        env_sel = self.query_one("#sel-env-type", Select)
        tier_sel = self.query_one("#sel-node-tier", Select)
        cuda_sel = self.query_one("#sel-cuda", Select)

        install_path = path_input.value.strip() or str(self.install_path)
        env_type = str(env_sel.value) if env_sel.value is not Select.BLANK else "venv"
        node_tier = str(tier_sel.value) if tier_sel.value is not Select.BLANK else "full"
        cuda = str(cuda_sel.value) if cuda_sel.value is not Select.BLANK else ""

        # Use --path from the input field
        args = f"install --type {env_type} --nodes {node_tier} --path {install_path}"
        if cuda:
            args += f" --cuda {cuda}"

        self.app.exit(result=args)

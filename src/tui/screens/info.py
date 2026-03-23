"""
Info Screen — Display system information.

Queries the ComfyUI venv (if present) for accurate PyTorch info.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult


def _get_venv_python(install_path: Path) -> Path | None:
    """Find the ComfyUI venv Python executable."""
    # Venv is at install_path/scripts/venv/ (see environment.py)
    if sys.platform == "win32":
        venv_python = install_path / "scripts" / "venv" / "Scripts" / "python.exe"
    else:
        venv_python = install_path / "scripts" / "venv" / "bin" / "python"
    return venv_python if venv_python.exists() else None


def _query_venv(venv_python: Path, code: str) -> str | None:
    """Run a Python snippet in the venv and return stdout."""
    try:
        result = subprocess.run(  # noqa: S603
            [str(venv_python), "-c", code],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _build_info_text(install_path: Path) -> str:
    """Build formatted system info string."""
    lines = ["[b]ℹ️  System Information[/b]\n"]

    venv_python = _get_venv_python(install_path)

    # Python — show venv Python version if available
    if venv_python:
        venv_ver = _query_venv(venv_python, "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
        lines.append(f"[b]Python:[/b]    {venv_ver or '?'} [dim](ComfyUI venv)[/dim]")
    else:
        lines.append(f"[b]Python:[/b]    {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} [dim](system)[/dim]")
    lines.append(f"[b]Platform:[/b]  {sys.platform}")

    # GPU
    try:
        from src.utils.gpu import get_gpu_vram_info, recommend_model_quality
        gpu = get_gpu_vram_info()
        if gpu:
            lines.append(f"\n[b]GPU:[/b]       {gpu.name}")
            lines.append(f"[b]VRAM:[/b]      {gpu.vram_gib} GB")
            lines.append(f"[b]Quality:[/b]   {recommend_model_quality(gpu.vram_gib)}")
        else:
            lines.append("\n[b]GPU:[/b]       [dim]Not detected[/dim]")
    except Exception:
        lines.append("\n[b]GPU:[/b]       [dim]Detection unavailable[/dim]")

    # PyTorch — query from venv
    if venv_python:
        torch_info = _query_venv(venv_python, (
            "import torch; "
            "cuda = f' (CUDA {torch.version.cuda})' if torch.cuda.is_available() else ''; "
            "print(f'{torch.__version__}{cuda}')"
        ))
        if torch_info:
            lines.append(f"\n[b]PyTorch:[/b]   {torch_info}")
        else:
            lines.append("\n[b]PyTorch:[/b]   [dim]Not installed in venv[/dim]")
    else:
        lines.append("\n[b]PyTorch:[/b]   [dim]No venv found[/dim]")

    # Tools
    try:
        from src.utils.commands import check_command_exists, get_command_version
        git_ver = get_command_version("git")
        lines.append(f"\n[b]Git:[/b]       {git_ver or '[dim]Not installed[/dim]'}")
        aria2 = check_command_exists("aria2c")
        lines.append(f"[b]aria2c:[/b]    {'[green]Available[/green]' if aria2 else '[dim]Not installed[/dim]'}")
        uv_ver = get_command_version("uv", "version")
        lines.append(f"[b]uv:[/b]        {uv_ver or '[dim]Not installed[/dim]'}")
    except Exception:
        pass

    return "\n".join(lines)


class InfoScreen(Screen):
    """System information display."""

    BINDINGS = [("escape", "app.back", "Back")]

    def __init__(self, install_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.install_path = install_path

    def compose(self) -> ComposeResult:
        """Build the info layout."""
        yield Header(show_clock=True)
        with Vertical(id="info-container"):
            yield Static(_build_info_text(self.install_path), id="info-panel")
            with Center():
                yield Button("← Back", id="btn-back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle back button."""
        if event.button.id == "btn-back":
            self.app.pop_screen()

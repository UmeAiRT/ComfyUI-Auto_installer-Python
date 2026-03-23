"""
Info Screen — Display system information.

Queries the ComfyUI venv (if present) for accurate package info.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.containers import Center, VerticalScroll
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
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


# Single venv query to get all package versions at once (faster)
_VENV_PACKAGES_SCRIPT = """
import sys, json
info = {"python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"}
try:
    import torch
    info["torch"] = torch.__version__
    if torch.cuda.is_available():
        info["cuda"] = torch.version.cuda
except ImportError:
    pass
for pkg in ("sageattention", "triton", "xformers"):
    try:
        mod = __import__(pkg)
        info[pkg] = getattr(mod, "__version__", "installed")
    except ImportError:
        pass
print(json.dumps(info))
"""


def _count_custom_nodes(install_path: Path) -> int | None:
    """Count installed custom nodes (directories in ComfyUI/custom_nodes/)."""
    nodes_dir = install_path / "custom_nodes"
    if not nodes_dir.is_dir():
        return None
    # Count subdirectories that look like nodes (have __init__.py or *.py)
    count = 0
    for child in nodes_dir.iterdir():
        if child.is_dir() and child.name not in ("__pycache__", ".git"):
            count += 1
    return count


def _get_comfyui_version(install_path: Path) -> str | None:
    """Get ComfyUI git version (short hash + date)."""
    comfy_dir = install_path / "ComfyUI"
    if not comfy_dir.is_dir():
        return None
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "log", "-1", "--format=%h (%ci)"],
            capture_output=True, text=True, timeout=5,
            cwd=str(comfy_dir),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_disk_usage(install_path: Path) -> str | None:
    """Get total size of models directory."""
    models_dir = install_path / "models"
    if not models_dir.is_dir():
        return None
    try:
        total = sum(f.stat().st_size for f in models_dir.rglob("*") if f.is_file())
        if total > 1_073_741_824:  # > 1 GB
            return f"{total / 1_073_741_824:.1f} GB"
        return f"{total / 1_048_576:.0f} MB"
    except Exception:
        return None


def _build_info_text(install_path: Path) -> str:
    """Build formatted system info string."""
    lines = ["[b]ℹ️  System Information[/b]\n"]

    venv_python = _get_venv_python(install_path)

    # ── Query all venv packages in one shot ──
    pkg_info: dict = {}
    if venv_python:
        raw = _query_venv(venv_python, _VENV_PACKAGES_SCRIPT)
        if raw:
            import json
            try:
                pkg_info = json.loads(raw)
            except json.JSONDecodeError:
                pass

    # ── Environment ──
    lines.append("[b]── Environment ──[/b]")
    if pkg_info.get("python"):
        lines.append(f"[b]Python:[/b]         {pkg_info['python']} [dim](ComfyUI venv)[/dim]")
    else:
        lines.append(f"[b]Python:[/b]         {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} [dim](system)[/dim]")
    lines.append(f"[b]Platform:[/b]       {sys.platform}")

    # ── GPU ──
    lines.append("\n[b]── GPU ──[/b]")
    try:
        from src.utils.gpu import get_gpu_vram_info
        gpu = get_gpu_vram_info()
        if gpu:
            lines.append(f"[b]GPU:[/b]            {gpu.name}")
            lines.append(f"[b]VRAM:[/b]           {gpu.vram_gib} GB")
        else:
            lines.append("[b]GPU:[/b]            [dim]Not detected[/dim]")
    except Exception:
        lines.append("[b]GPU:[/b]            [dim]Detection unavailable[/dim]")

    # ── ML Packages (from venv) ──
    lines.append("\n[b]── ML Packages ──[/b]")
    if pkg_info.get("torch"):
        cuda_str = f" [green](CUDA {pkg_info['cuda']})[/green]" if pkg_info.get("cuda") else ""
        lines.append(f"[b]PyTorch:[/b]        {pkg_info['torch']}{cuda_str}")
    elif venv_python:
        lines.append("[b]PyTorch:[/b]        [dim]Not installed[/dim]")
    else:
        lines.append("[b]PyTorch:[/b]        [dim]No venv found[/dim]")

    # SageAttention
    if pkg_info.get("sageattention"):
        lines.append(f"[b]SageAttention:[/b]  [green]{pkg_info['sageattention']}[/green]")
    elif venv_python:
        lines.append("[b]SageAttention:[/b]  [dim]Not installed[/dim]")

    # Triton
    if pkg_info.get("triton"):
        lines.append(f"[b]Triton:[/b]         [green]{pkg_info['triton']}[/green]")
    elif venv_python:
        lines.append("[b]Triton:[/b]         [dim]Not installed[/dim]")

    # xformers
    if pkg_info.get("xformers"):
        lines.append(f"[b]xformers:[/b]       [green]{pkg_info['xformers']}[/green]")
    elif venv_python:
        lines.append("[b]xformers:[/b]       [dim]Not installed[/dim]")

    # ── ComfyUI ──
    comfy_ver = _get_comfyui_version(install_path)
    node_count = _count_custom_nodes(install_path)
    models_size = _get_disk_usage(install_path)

    if comfy_ver or node_count is not None or models_size:
        lines.append("\n[b]── ComfyUI ──[/b]")
        if comfy_ver:
            lines.append(f"[b]Version:[/b]        {comfy_ver}")
        if node_count is not None:
            lines.append(f"[b]Custom Nodes:[/b]   {node_count} installed")
        if models_size:
            lines.append(f"[b]Models:[/b]         {models_size}")

    # ── System Tools ──
    lines.append("\n[b]── Tools ──[/b]")
    try:
        from src.utils.commands import check_command_exists, get_command_version
        git_ver = get_command_version("git")
        lines.append(f"[b]Git:[/b]            {git_ver or '[dim]Not installed[/dim]'}")
        aria2 = check_command_exists("aria2c")
        lines.append(f"[b]aria2c:[/b]         {'[green]Available[/green]' if aria2 else '[dim]Not installed[/dim]'}")
        uv_ver = get_command_version("uv", "version")
        lines.append(f"[b]uv:[/b]             {uv_ver or '[dim]Not installed[/dim]'}")
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
        with VerticalScroll(id="info-container"):
            yield Static(_build_info_text(self.install_path), id="info-panel")
            with Center():
                yield Button("← Back", id="btn-back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle back button."""
        if event.button.id == "btn-back":
            self.app.pop_screen()

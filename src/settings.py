"""
Persistent user settings for UmeAiRT ComfyUI.

Settings are stored as JSON and read by the TUI and launcher.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pathlib import Path


class UserSettings(BaseModel):
    """User-configurable settings for ComfyUI launcher."""

    listen_address: str = "127.0.0.1"
    vram_mode: str = Field(
        default="auto",
        description="VRAM mode: auto, normal, low, high",
    )
    use_sage_attention: bool = True
    auto_launch_browser: bool = True
    extra_args: list[str] = Field(default_factory=list)

    @staticmethod
    def settings_path(install_path: Path) -> Path:
        """Return the path to the settings file."""
        return install_path / "scripts" / "user_settings.json"

    @classmethod
    def load(cls, install_path: Path) -> UserSettings:
        """Load settings from disk, returning defaults if not found."""
        path = cls.settings_path(install_path)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls.model_validate(data)
            except (json.JSONDecodeError, ValueError):
                pass
        return cls()

    def save(self, install_path: Path) -> None:
        """Save settings to disk."""
        path = self.settings_path(install_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(), indent=2),
            encoding="utf-8",
        )

    def build_comfyui_args(self) -> list[str]:
        """Build the ComfyUI command-line arguments from settings."""
        args = ["--listen", self.listen_address]

        if self.use_sage_attention:
            args.append("--use-sage-attention")

        if self.auto_launch_browser:
            args.append("--auto-launch")

        if self.vram_mode == "low":
            args.extend(["--lowvram", "--disable-smart-memory", "--fp8_e4m3fn-text-enc"])
        elif self.vram_mode == "high":
            args.append("--highvram")

        # DirectML for AMD on Windows
        try:
            import sys as _sys
            if _sys.platform == "win32":
                from src.utils.gpu import check_amd_gpu
                if check_amd_gpu():
                    args.append("--directml")
        except Exception:
            pass

        args.extend(self.extra_args)
        return args

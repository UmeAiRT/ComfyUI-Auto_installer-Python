"""Snapshot tests for generated launcher and tool scripts.

Verifies that the generated .bat/.sh scripts contain expected
patterns without relying on exact content matching.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path


class TestBatLauncher:
    """Tests for Windows .bat launcher generation."""

    def test_bat_launcher_contains_python_call(self, tmp_path: Path) -> None:
        """Performance launcher should reference python and main.py."""
        from src.installer.finalize import _write_bat_launcher

        log = MagicMock()
        _write_bat_launcher(
            tmp_path, "UmeAiRT-Start-ComfyUI", "Performance Mode",
            "--use-sage-attention --auto-launch", log,
        )

        script = tmp_path / "UmeAiRT-Start-ComfyUI.bat"
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "python" in content.lower() or "main.py" in content
        assert "--use-sage-attention" in content
        assert "--auto-launch" in content

    def test_lowvram_bat_has_flags(self, tmp_path: Path) -> None:
        """LowVRAM launcher should include --lowvram and --fp8 flags."""
        from src.installer.finalize import _write_bat_launcher

        log = MagicMock()
        args = "--use-sage-attention --auto-launch --disable-smart-memory --lowvram --fp8_e4m3fn-text-enc"
        _write_bat_launcher(
            tmp_path, "UmeAiRT-Start-ComfyUI_LowVRAM", "Low VRAM Mode",
            args, log,
        )

        script = tmp_path / "UmeAiRT-Start-ComfyUI_LowVRAM.bat"
        content = script.read_text(encoding="utf-8")
        assert "--lowvram" in content
        assert "--fp8" in content
        assert "--disable-smart-memory" in content

    def test_directml_bat_has_directml_flag(self, tmp_path: Path) -> None:
        """DirectML launcher should include --directml flag."""
        from src.installer.finalize import _write_bat_launcher

        log = MagicMock()
        _write_bat_launcher(
            tmp_path, "Test-DirectML", "DirectML Mode",
            "--directml --use-sage-attention --auto-launch", log,
        )

        script = tmp_path / "Test-DirectML.bat"
        content = script.read_text(encoding="utf-8")
        assert "--directml" in content


class TestBatTool:
    """Tests for Windows .bat tool script generation."""

    def test_update_tool_calls_update_command(self, tmp_path: Path) -> None:
        """Update tool should contain the update CLI command."""
        from src.installer.finalize import _write_bat_tool

        log = MagicMock()
        _write_bat_tool(
            tmp_path, "UmeAiRT-Update", "Updater",
            'umeairt-comfyui-installer update --path "%InstallPath%"', log,
        )

        script = tmp_path / "UmeAiRT-Update.bat"
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "umeairt-comfyui-installer update" in content

    def test_downloader_tool_calls_download_command(self, tmp_path: Path) -> None:
        """Downloader tool should contain the download-models CLI command."""
        from src.installer.finalize import _write_bat_tool

        log = MagicMock()
        _write_bat_tool(
            tmp_path, "UmeAiRT-Download-Models", "Model Downloader",
            'umeairt-comfyui-installer download-models --path "%InstallPath%"', log,
        )

        script = tmp_path / "UmeAiRT-Download-Models.bat"
        content = script.read_text(encoding="utf-8")
        assert "download-models" in content

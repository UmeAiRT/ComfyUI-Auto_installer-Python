"""Tests for UserSettings model."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path


class TestUserSettingsDefaults:
    """Tests for default settings values."""

    def test_default_listen_address(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        assert s.listen_address == "127.0.0.1"

    def test_default_vram_mode(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        assert s.vram_mode == "auto"

    def test_default_sage_attention(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        assert s.use_sage_attention is True

    def test_default_auto_launch_browser(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        assert s.auto_launch_browser is True

    def test_default_extra_args_empty(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        assert s.extra_args == []


class TestUserSettingsPersistence:
    """Tests for save/load round-trip."""

    def test_settings_path(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        path = UserSettings.settings_path(tmp_path)
        assert path == tmp_path / "scripts" / "user_settings.json"

    def test_save_creates_file(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        s = UserSettings(listen_address="0.0.0.0")
        s.save(tmp_path)
        assert UserSettings.settings_path(tmp_path).exists()

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        nested = tmp_path / "deep" / "nested"
        s = UserSettings()
        s.save(nested)
        assert UserSettings.settings_path(nested).exists()

    def test_load_round_trip(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        original = UserSettings(
            listen_address="0.0.0.0",
            vram_mode="high",
            use_sage_attention=False,
            auto_launch_browser=False,
            extra_args=["--foo", "--bar"],
        )
        original.save(tmp_path)
        loaded = UserSettings.load(tmp_path)
        assert loaded.listen_address == "0.0.0.0"
        assert loaded.vram_mode == "high"
        assert loaded.use_sage_attention is False
        assert loaded.auto_launch_browser is False
        assert loaded.extra_args == ["--foo", "--bar"]

    def test_load_returns_defaults_if_missing(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        loaded = UserSettings.load(tmp_path)
        assert loaded.listen_address == "127.0.0.1"
        assert loaded.vram_mode == "auto"

    def test_load_returns_defaults_on_corrupt_json(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        path = UserSettings.settings_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("not valid json {{", encoding="utf-8")
        loaded = UserSettings.load(tmp_path)
        assert loaded.listen_address == "127.0.0.1"

    def test_load_returns_defaults_on_invalid_schema(self, tmp_path: Path) -> None:
        from src.settings import UserSettings
        path = UserSettings.settings_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"listen_address": 12345}), encoding="utf-8")
        # Pydantic should coerce or reject; either way, should not crash
        loaded = UserSettings.load(tmp_path)
        assert loaded is not None


class TestBuildComfyuiArgs:
    """Tests for build_comfyui_args()."""

    def test_default_args_include_listen_and_sage(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        args = s.build_comfyui_args()
        assert "--listen" in args
        assert "127.0.0.1" in args
        assert "--use-sage-attention" in args
        assert "--auto-launch" in args

    def test_sage_disabled(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(use_sage_attention=False)
        args = s.build_comfyui_args()
        assert "--use-sage-attention" not in args

    def test_auto_launch_disabled(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(auto_launch_browser=False)
        args = s.build_comfyui_args()
        assert "--auto-launch" not in args

    def test_low_vram_mode(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(vram_mode="low")
        args = s.build_comfyui_args()
        assert "--lowvram" in args
        assert "--disable-smart-memory" in args
        assert "--fp8_e4m3fn-text-enc" in args

    def test_high_vram_mode(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(vram_mode="high")
        args = s.build_comfyui_args()
        assert "--highvram" in args
        assert "--lowvram" not in args

    def test_normal_vram_mode_no_flags(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(vram_mode="normal")
        args = s.build_comfyui_args()
        assert "--highvram" not in args
        assert "--lowvram" not in args

    def test_custom_listen_address(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(listen_address="0.0.0.0")
        args = s.build_comfyui_args()
        assert args[0:2] == ["--listen", "0.0.0.0"]

    def test_extra_args_appended(self) -> None:
        from src.settings import UserSettings
        s = UserSettings(extra_args=["--custom-flag", "--other"])
        args = s.build_comfyui_args()
        assert "--custom-flag" in args
        assert "--other" in args

    @patch("sys.platform", "win32")
    def test_directml_on_windows_with_amd(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        with patch("src.utils.gpu.check_amd_gpu", return_value=True):
            args = s.build_comfyui_args()
            assert "--directml" in args

    @patch("sys.platform", "win32")
    def test_no_directml_on_windows_without_amd(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        with patch("src.utils.gpu.check_amd_gpu", return_value=False):
            args = s.build_comfyui_args()
            assert "--directml" not in args

    @patch("sys.platform", "linux")
    def test_no_directml_on_linux(self) -> None:
        from src.settings import UserSettings
        s = UserSettings()
        args = s.build_comfyui_args()
        assert "--directml" not in args

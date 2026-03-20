"""Tests for the finalization module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path


class TestInstallComfySettings:
    """Tests for install_comfy_settings."""

    def test_copies_settings(self, tmp_path: Path) -> None:
        """Should copy comfy.settings.json to user/default/."""
        from src.installer.finalize import install_comfy_settings

        log = MagicMock()

        # Create source settings
        source_dir = tmp_path / "source_scripts"
        source_dir.mkdir()
        settings_file = source_dir / "comfy.settings.json"
        settings_file.write_text('{"key": "value"}', encoding="utf-8")

        with patch("src.installer.environment.find_source_scripts", return_value=source_dir):
            install_path = tmp_path / "install"
            install_comfy_settings(install_path, log)

            dest = install_path / "user" / "default" / "comfy.settings.json"
            assert dest.exists()
            assert dest.read_text(encoding="utf-8") == '{"key": "value"}'

    def test_skips_if_source_missing(self, tmp_path: Path) -> None:
        """Should skip if source scripts dir not found."""
        from src.installer.finalize import install_comfy_settings

        log = MagicMock()

        with patch("src.installer.environment.find_source_scripts", side_effect=FileNotFoundError):
            install_comfy_settings(tmp_path, log)
            log.warning.assert_called_once()

    def test_skips_if_settings_file_missing(self, tmp_path: Path) -> None:
        """Should skip if comfy.settings.json not in source."""
        from src.installer.finalize import install_comfy_settings

        log = MagicMock()

        source_dir = tmp_path / "source_scripts"
        source_dir.mkdir()

        with patch("src.installer.environment.find_source_scripts", return_value=source_dir):
            install_comfy_settings(tmp_path, log)
            log.warning.assert_called_once()

    def test_skips_if_up_to_date(self, tmp_path: Path) -> None:
        """Should skip if dest settings are newer than source."""
        import time

        from src.installer.finalize import install_comfy_settings

        log = MagicMock()

        source_dir = tmp_path / "source_scripts"
        source_dir.mkdir()
        settings_file = source_dir / "comfy.settings.json"
        settings_file.write_text('{"old": true}', encoding="utf-8")

        # Create a newer dest file
        install_path = tmp_path / "install"
        dest = install_path / "user" / "default" / "comfy.settings.json"
        dest.parent.mkdir(parents=True)
        time.sleep(0.05)
        dest.write_text('{"new": true}', encoding="utf-8")

        with patch("src.installer.environment.find_source_scripts", return_value=source_dir):
            install_comfy_settings(install_path, log)

            # Dest should be unchanged
            assert dest.read_text(encoding="utf-8") == '{"new": true}'


class TestOfferModelDownloads:
    """Tests for offer_model_downloads."""

    def test_no_catalog_found(self, tmp_path: Path) -> None:
        """Should log info if no catalog exists anywhere."""
        from src.installer.finalize import offer_model_downloads

        log = MagicMock()

        with patch("src.installer.environment.find_source_scripts", side_effect=FileNotFoundError):
            offer_model_downloads(tmp_path, log)

        log.info.assert_called()

    def test_catalog_found_user_declines(self, tmp_path: Path) -> None:
        """Should respect user declining downloads."""
        from src.installer.finalize import offer_model_downloads

        log = MagicMock()
        catalog = tmp_path / "scripts" / "model_manifest.json"
        catalog.parent.mkdir(parents=True)
        catalog.write_text("{}", encoding="utf-8")

        with patch("src.installer.finalize.confirm", return_value=False):
            offer_model_downloads(tmp_path, log)

        log.sub.assert_called()


class TestCreateLaunchers:
    """Tests for create_launchers."""

    def test_creates_bat_launchers_on_windows(self, tmp_path: Path) -> None:
        """Should create .bat files on Windows."""
        from src.installer.finalize import create_launchers

        log = MagicMock()

        with patch("src.installer.finalize.sys") as mock_sys:
            mock_sys.platform = "win32"
            with (
                patch("src.installer.finalize._write_bat_launcher") as mock_bat,
                patch("src.installer.finalize._write_bat_tool") as mock_tool,
            ):
                create_launchers(tmp_path, log)
                assert mock_bat.call_count == 2  # Performance + LowVRAM
                assert mock_tool.call_count == 2  # Download + Update

    def test_creates_sh_launchers_on_linux(self, tmp_path: Path) -> None:
        """Should create .sh files on Linux."""
        from src.installer.finalize import create_launchers

        log = MagicMock()

        with patch("src.installer.finalize.sys") as mock_sys:
            mock_sys.platform = "linux"
            with (
                patch("src.installer.finalize._write_sh_launcher") as mock_sh,
                patch("src.installer.finalize._write_sh_tool") as mock_tool,
            ):
                create_launchers(tmp_path, log)
                assert mock_sh.call_count == 2
                assert mock_tool.call_count == 2

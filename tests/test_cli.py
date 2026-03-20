"""Tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli import _clean_path, app

runner = CliRunner()


class TestCleanPath:
    """Tests for _clean_path helper."""

    def test_strips_double_quotes(self) -> None:
        assert _clean_path(Path('"C:\\foo\\bar"')) == Path("C:\\foo\\bar")

    def test_no_op_on_clean_path(self) -> None:
        assert _clean_path(Path("C:\\foo\\bar")) == Path("C:\\foo\\bar")

    def test_preserves_inner_content(self) -> None:
        assert _clean_path(Path('"path with spaces"')) == Path("path with spaces")

    def test_empty_quotes(self) -> None:
        assert _clean_path(Path('""')) == Path("")


class TestVersionCommand:
    """Tests for the version CLI command."""

    def test_shows_version(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "comfyui-installer v" in result.output


class TestInfoCommand:
    """Tests for the info CLI command."""

    def test_info_runs(self) -> None:
        """Info command should succeed and display table."""
        with (
            patch("src.utils.gpu.get_gpu_vram_info", return_value=None),
            patch("src.utils.commands.check_command_exists", return_value=False),
            patch("src.utils.commands.get_command_version", return_value=None),
        ):
            result = runner.invoke(app, ["info"])
            assert result.exit_code == 0
            assert "System Information" in result.output

    def test_info_with_gpu(self) -> None:
        """Info command should display GPU info when detected."""
        mock_gpu = MagicMock()
        mock_gpu.name = "Test GPU"
        mock_gpu.vram_gib = 12.0
        with (
            patch("src.utils.gpu.get_gpu_vram_info", return_value=mock_gpu),
            patch("src.utils.gpu.recommend_model_quality", return_value="High"),
            patch("src.utils.commands.check_command_exists", return_value=True),
            patch("src.utils.commands.get_command_version", return_value="2.47.1"),
        ):
            result = runner.invoke(app, ["info"])
            assert result.exit_code == 0
            assert "Test GPU" in result.output


class TestInstallCommand:
    """Tests for the install CLI command."""

    def test_install_calls_run_install(self, tmp_path: Path) -> None:
        """Install command should call run_install with correct args."""
        with patch("src.installer.install.run_install") as mock_run:
            result = runner.invoke(app, [
                "install",
                "--path", str(tmp_path),
                "--type", "venv",
                "--nodes", "minimal",
            ])
            assert result.exit_code == 0
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][1] == "venv"
            assert call_args[1]["node_tier"] == "minimal"


class TestUpdateCommand:
    """Tests for the update CLI command."""

    def test_update_calls_run_update(self, tmp_path: Path) -> None:
        """Update command should call run_update."""
        with patch("src.installer.updater.run_update") as mock_run:
            result = runner.invoke(app, [
                "update",
                "--path", str(tmp_path),
            ])
            assert result.exit_code == 0
            mock_run.assert_called_once()


class TestDownloadModelsCommand:
    """Tests for the download-models CLI command."""

    def test_missing_catalog_exits_with_error(self, tmp_path: Path) -> None:
        """Should exit with code 1 if catalog file doesn't exist."""
        result = runner.invoke(app, [
            "download-models",
            "--path", str(tmp_path),
            "--catalog", str(tmp_path / "nonexistent.json"),
        ])
        assert result.exit_code == 1

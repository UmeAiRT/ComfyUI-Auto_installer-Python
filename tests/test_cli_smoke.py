"""Smoke tests for the CLI entry point."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


class TestCLISmoke:
    """Verify the CLI wires up correctly without running the installer."""

    def test_help_shows_version(self) -> None:
        """--help should include the app name and show available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "comfyui-installer" in result.output.lower() or "install" in result.output.lower()

    def test_install_help(self) -> None:
        """install --help should show all expected options."""
        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--type" in result.output
        assert "--nodes" in result.output
        assert "--yes" in result.output
        assert "--verbose" in result.output

    def test_update_help(self) -> None:
        """update --help should show all expected options."""
        result = runner.invoke(app, ["update", "--help"])
        assert result.exit_code == 0
        assert "--path" in result.output
        assert "--verbose" in result.output
        assert "--yes" in result.output

    def test_install_invalid_type(self) -> None:
        """install --type invalid should fail with a helpful error."""
        result = runner.invoke(app, ["install", "--type", "invalid"])
        assert result.exit_code != 0
        assert "invalid" in result.output.lower() or "Invalid" in result.output

    def test_install_invalid_nodes(self) -> None:
        """install --nodes bogus should fail with a helpful error."""
        result = runner.invoke(app, ["install", "--nodes", "bogus"])
        assert result.exit_code != 0
        assert "bogus" in result.output.lower() or "Invalid" in result.output

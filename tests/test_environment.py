"""Tests for the environment setup module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.installer.environment import find_source_scripts


class TestFindSourceScripts:
    """Tests for find_source_scripts."""

    def test_finds_scripts_from_package_root(self) -> None:
        """Should find scripts/ relative to the package root."""
        result = find_source_scripts()
        if result is not None:
            assert result.is_dir()
            assert (result / "dependencies.json").exists()

    def test_returns_path_object(self) -> None:
        """Should return a Path (or raise FileNotFoundError)."""
        try:
            result = find_source_scripts()
            assert isinstance(result, Path)
        except OSError:
            pass


class TestCreateVenvWithUv:
    """Tests for _create_venv_with_uv (extracted helper)."""

    def test_system_python_succeeds(self) -> None:
        """When system Python works, no fallback is needed."""
        from src.installer.environment import _create_venv_with_uv

        log = MagicMock()
        venv_path = Path("/tmp/test_venv")

        with patch("src.installer.environment.run_and_log") as mock_run:
            _create_venv_with_uv("uv", venv_path, log)

            # Should have been called once (system Python — no fallback)
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "uv" in args[0]
            assert "--python-preference" in args[1]
            assert "only-system" in args[1]

    def test_fallback_to_managed_python(self) -> None:
        """When system Python fails, should try managed Python."""
        from src.installer.environment import _create_venv_with_uv
        from src.utils.commands import CommandError

        log = MagicMock()
        venv_path = Path("/tmp/test_venv")

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise CommandError("uv", 1, "no system python")
            # Second call succeeds

        with patch("src.installer.environment.run_and_log", side_effect=side_effect):
            _create_venv_with_uv("uv", venv_path, log)
            assert call_count == 2

    def test_both_fail_raises(self) -> None:
        """When both system and managed Python fail, should raise."""
        from src.installer.environment import _create_venv_with_uv
        from src.utils.commands import CommandError

        log = MagicMock()
        venv_path = Path("/tmp/test_venv")

        with (
            patch("src.installer.environment.run_and_log", side_effect=CommandError("uv", 1, "fail")),
            pytest.raises(CommandError),
        ):
            _create_venv_with_uv("uv", venv_path, log)


class TestProvisionScripts:
    """Tests for provision_scripts."""

    def test_creates_scripts_dir(self, tmp_path: Path) -> None:
        """Should create the scripts directory if it doesn't exist."""
        from src.installer.environment import provision_scripts

        log = MagicMock()
        install_path = tmp_path / "install"

        # Mock the source scripts location
        with patch("src.installer.environment.find_source_scripts") as mock_find:
            source_dir = tmp_path / "source_scripts"
            source_dir.mkdir()
            # Create minimal required files
            (source_dir / "dependencies.json").write_text("{}", encoding="utf-8")
            mock_find.return_value = source_dir

            provision_scripts(install_path, log)

            assert (install_path / "scripts").is_dir()

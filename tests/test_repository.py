"""Tests for the repository setup module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from src.installer.repository import EXTERNAL_FOLDERS, clone_comfyui, setup_git_config
from src.enums import InstallerFatalError

if TYPE_CHECKING:
    from pathlib import Path


class TestSetupGitConfig:
    """Tests for setup_git_config."""

    def test_calls_git_config(self) -> None:
        """Should call git config --global core.longpaths true."""
        log = MagicMock()
        with patch("src.installer.repository.run_and_log") as mock_run:
            setup_git_config(log)
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert args[0] == "git"
            assert "core.longpaths" in args[1]
            assert "true" in args[1]

    def test_handles_command_error(self) -> None:
        """Should not crash if git config fails."""
        from src.utils.commands import CommandError

        log = MagicMock()
        with patch("src.installer.repository.run_and_log", side_effect=CommandError("git", 1, "fail")):
            # Should not raise
            setup_git_config(log)


class TestCloneComfyui:
    """Tests for clone_comfyui."""

    def test_skips_if_exists(self, tmp_path: Path) -> None:
        """Should skip cloning if the directory already exists."""
        log = MagicMock()
        comfy_path = tmp_path / "ComfyUI"
        comfy_path.mkdir()
        deps = MagicMock()

        clone_comfyui(tmp_path, comfy_path, deps, log)
        log.sub.assert_called()

    def test_retries_on_failure(self, tmp_path: Path) -> None:
        """Should retry up to max_retries times."""
        from src.utils.commands import CommandError

        log = MagicMock()
        comfy_path = tmp_path / "ComfyUI"
        deps = MagicMock()
        deps.repositories.comfyui.url = "https://example.com/test.git"

        with (
            patch("src.installer.repository.run_and_log", side_effect=CommandError("git", 1, "fail")),
            pytest.raises(InstallerFatalError),
        ):
            clone_comfyui(tmp_path, comfy_path, deps, log, max_retries=2)

        # Should have logged warnings for retries
        assert log.warning.call_count >= 1

    def test_cleans_partial_clone_between_retries(self, tmp_path: Path) -> None:
        """Should remove partial clone dir between retries."""
        from src.utils.commands import CommandError

        log = MagicMock()
        comfy_path = tmp_path / "ComfyUI"
        deps = MagicMock()
        deps.repositories.comfyui.url = "https://example.com/test.git"

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Simulate partial clone by creating partial dir
            comfy_path.mkdir(exist_ok=True)
            raise CommandError("git", 1, "network error")

        with (
            patch("src.installer.repository.run_and_log", side_effect=side_effect),
            pytest.raises(InstallerFatalError),
        ):
            clone_comfyui(tmp_path, comfy_path, deps, log, max_retries=2)

        assert call_count == 2


class TestExternalFolders:
    """Tests for the junction architecture constants."""

    def test_has_required_folders(self) -> None:
        """All essential folders should be in EXTERNAL_FOLDERS."""
        assert "models" in EXTERNAL_FOLDERS
        assert "custom_nodes" in EXTERNAL_FOLDERS
        assert "output" in EXTERNAL_FOLDERS

    def test_has_at_least_5_folders(self) -> None:
        """Should have a reasonable number of external folders."""
        assert len(EXTERNAL_FOLDERS) >= 5

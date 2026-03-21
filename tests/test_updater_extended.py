"""Extended tests for the updater module — update_comfyui_core, update_custom_nodes, update_dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from src.enums import InstallerFatalError

if TYPE_CHECKING:
    from pathlib import Path


class TestUpdateComfyuiCore:
    """Tests for update_comfyui_core."""

    def test_pulls_latest(self, tmp_path: Path) -> None:
        """Should run git pull --ff-only."""
        from src.installer.updater import update_comfyui_core

        comfy_path = tmp_path / "ComfyUI"
        comfy_path.mkdir()

        log = MagicMock()
        with patch("src.installer.updater.run_and_log") as mock_run:
            update_comfyui_core(comfy_path, log)
            git_args = mock_run.call_args[0][1]
            assert "--ff-only" in git_args
            assert str(comfy_path) in git_args

    def test_missing_dir_logs_error(self, tmp_path: Path) -> None:
        """Should log error if ComfyUI dir doesn't exist."""
        from src.installer.updater import update_comfyui_core

        log = MagicMock()
        update_comfyui_core(tmp_path / "nonexistent", log)
        log.error.assert_called_once()

    def test_pull_failure_warns(self, tmp_path: Path) -> None:
        """Should warn on git pull failure (local changes)."""
        from src.installer.updater import update_comfyui_core
        from src.utils.commands import CommandError

        comfy_path = tmp_path / "ComfyUI"
        comfy_path.mkdir()

        log = MagicMock()
        with patch(
            "src.installer.updater.run_and_log",
            side_effect=CommandError("git", 1, "diverged"),
        ):
            update_comfyui_core(comfy_path, log)
            log.warning.assert_called_once()


class TestUpdateCustomNodes:
    """Tests for update_custom_nodes."""

    def test_skips_when_no_manifest(self, tmp_path: Path) -> None:
        """Should call skip_step when manifest is missing."""
        from src.installer.updater import update_custom_nodes

        install_path = tmp_path / "install"
        (install_path / "scripts").mkdir(parents=True)
        comfy_path = tmp_path / "ComfyUI"

        log = MagicMock()
        with patch("src.installer.environment.find_source_scripts", return_value=None):
            update_custom_nodes(MagicMock(), comfy_path, install_path, log)
            log.skip_step.assert_called_once()


class TestDetectPythonExtended:
    """Additional tests for _detect_python."""

    def test_conda_type_returns_conda_python(self, tmp_path: Path) -> None:
        """Should detect conda Python when install_type is 'conda'."""
        import sys

        from src.installer.updater import _detect_python

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "install_type").write_text("conda", encoding="utf-8")

        # Create fake conda python
        if sys.platform == "win32":
            conda_py = scripts_dir / "conda_env" / "python.exe"
        else:
            conda_py = scripts_dir / "conda_env" / "bin" / "python"
        conda_py.parent.mkdir(parents=True)
        conda_py.touch()

        log = MagicMock()
        result = _detect_python(scripts_dir, log)
        assert result == conda_py

    def test_conda_python_missing_raises(self, tmp_path: Path) -> None:
        """Should raise InstallerFatalError if conda Python not found."""
        from src.installer.updater import _detect_python

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "install_type").write_text("conda", encoding="utf-8")

        log = MagicMock()
        with pytest.raises(InstallerFatalError):
            _detect_python(scripts_dir, log)


class TestScanModelsWarning:
    """Tests for _scan_models_warning."""

    def test_no_models_dir(self, tmp_path: Path) -> None:
        """Should log and return if models dir doesn't exist."""
        from src.installer.updater import _scan_models_warning

        log = MagicMock()
        _scan_models_warning(tmp_path, log)
        log.sub.assert_called_once()
        assert "No models" in log.sub.call_args[0][0]

    def test_scanner_unavailable(self, tmp_path: Path) -> None:
        """Should handle scanner import failure gracefully."""
        from src.installer.updater import _scan_models_warning

        models_dir = tmp_path / "models"
        models_dir.mkdir()

        log = MagicMock()
        with patch(
            "src.utils.model_scanner.scan_models_directory",
            side_effect=Exception("scanner broken"),
        ):
            # This should not raise — it catches all exceptions
            _scan_models_warning(tmp_path, log)
            log.sub.assert_any_call(
                "Scanner unavailable. Install picklescan for model scanning.", style="dim"
            )

    def test_no_pickle_models(self, tmp_path: Path) -> None:
        """Should report clean when no pickle files found."""
        from src.installer.updater import _scan_models_warning

        models_dir = tmp_path / "models"
        models_dir.mkdir()

        mock_summary = MagicMock(total_scanned=0, unsafe_count=0)
        log = MagicMock()
        with patch(
            "src.utils.model_scanner.scan_models_directory",
            return_value=mock_summary,
        ):
            _scan_models_warning(tmp_path, log)
            log.sub.assert_any_call("No pickle-based model files found. All safe! ✅", style="success")

    def test_unsafe_models_warns(self, tmp_path: Path) -> None:
        """Should warn when unsafe models detected."""
        from src.installer.updater import _scan_models_warning

        models_dir = tmp_path / "models"
        models_dir.mkdir()

        mock_summary = MagicMock(total_scanned=5, unsafe_count=2)
        log = MagicMock()
        with patch(
            "src.utils.model_scanner.scan_models_directory",
            return_value=mock_summary,
        ):
            _scan_models_warning(tmp_path, log)
            log.warning.assert_called_once()

    def test_all_models_clean(self, tmp_path: Path) -> None:
        """Should report all clean when no unsafe files."""
        from src.installer.updater import _scan_models_warning

        models_dir = tmp_path / "models"
        models_dir.mkdir()

        mock_summary = MagicMock(total_scanned=10, unsafe_count=0)
        log = MagicMock()
        with patch(
            "src.utils.model_scanner.scan_models_directory",
            return_value=mock_summary,
        ):
            _scan_models_warning(tmp_path, log)

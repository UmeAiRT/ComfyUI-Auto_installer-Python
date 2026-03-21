"""Mocked end-to-end test for the install orchestrator.

Ensures the 12-step flow executes completely without errors and
that TOTAL_STEPS stays synchronized with actual log.step() calls.
"""

from __future__ import annotations

import json
from contextlib import ExitStack
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path


class TestRunInstallIntegration:
    """Mocked end-to-end test for run_install()."""

    def test_full_install_completes_all_steps(self, tmp_path: Path) -> None:
        """run_install() should execute all 12 steps without crashing.

        Mocks all external I/O (subprocess, git, downloads, etc.)
        and verifies the logger's step() is called TOTAL_STEPS times.
        """
        from src.installer.install import TOTAL_STEPS, run_install

        # Create minimum required files
        scripts = tmp_path / "scripts"
        scripts.mkdir(parents=True)

        deps_data = {
            "repositories": {"comfyui": {"url": "https://example.com"}},
            "pip_packages": {
                "comfyui_requirements": "requirements.txt",
                "torch": {"cu130": {"packages": "torch", "index_url": "https://x"}},
                "packages": [],
            },
            "tools": {
                "git_windows": {"url": "https://example.com", "sha256": "abc"},
                "aria2_windows": {"url": "https://example.com", "sha256": "def"},
            },
        }
        (scripts / "dependencies.json").write_text(json.dumps(deps_data), encoding="utf-8")

        source_dir = tmp_path / "source_scripts"
        source_dir.mkdir()
        (source_dir / "dependencies.json").write_text(json.dumps(deps_data), encoding="utf-8")

        # Track step calls via a wrapper
        step_calls: list[str] = []

        def mock_setup_logger(**kwargs):
            from src.utils.logging import setup_logger
            log = setup_logger(
                log_file=tmp_path / "logs" / "test.log",
                total_steps=TOTAL_STEPS,
                verbose=False,
            )
            original_step = log.step

            def tracking_step(title, *args, **kw):
                step_calls.append(title)
                return original_step(title, *args, **kw)

            log.step = tracking_step
            return log

        mock_platform = MagicMock()
        mock_platform.name = "windows"

        # Use ExitStack to avoid Python 3.11 "too many nested blocks" syntax error
        with ExitStack() as stack:
            stack.enter_context(patch("src.installer.install.setup_logger", side_effect=mock_setup_logger))
            stack.enter_context(patch("src.installer.install.get_platform", return_value=mock_platform))
            stack.enter_context(patch("src.installer.install.load_settings"))
            stack.enter_context(patch("src.installer.install.check_prerequisites", return_value=True))
            stack.enter_context(patch("src.installer.install.install_git", return_value=True))
            stack.enter_context(patch("src.installer.install.ensure_aria2"))
            stack.enter_context(patch("src.installer.install.setup_environment", return_value=tmp_path / "py.exe"))
            stack.enter_context(patch("src.installer.install.provision_scripts"))
            stack.enter_context(patch("src.installer.environment.find_source_scripts", return_value=source_dir))
            stack.enter_context(patch("src.installer.install.setup_git_config"))
            stack.enter_context(patch("src.installer.install.clone_comfyui"))
            stack.enter_context(patch("src.installer.install.setup_junction_architecture"))
            stack.enter_context(patch("src.installer.gpu_setup.detect_and_select_gpu", return_value="cu130"))
            stack.enter_context(patch("src.installer.install.install_core_dependencies"))
            stack.enter_context(patch("src.installer.install.install_python_packages"))
            stack.enter_context(patch("src.installer.install.install_wheels"))
            stack.enter_context(patch("src.installer.install.install_custom_nodes", return_value=(5, 5)))
            stack.enter_context(patch("src.installer.install.install_optimizations"))
            stack.enter_context(patch("src.installer.install.install_cli_in_environment"))
            stack.enter_context(patch("src.installer.install.install_comfy_settings"))
            stack.enter_context(patch("src.installer.install.create_launchers"))
            stack.enter_context(patch("src.installer.install.offer_model_downloads"))
            stack.enter_context(patch("src.installer.install.confirm", return_value=True))

            run_install(tmp_path, verbose=False)

        assert len(step_calls) == TOTAL_STEPS, (
            f"Expected {TOTAL_STEPS} log.step() calls but got {len(step_calls)}. "
            f"Steps seen: {step_calls}"
        )

    def test_total_steps_constant_matches_code(self) -> None:
        """TOTAL_STEPS should be 12."""
        from src.installer.install import TOTAL_STEPS
        assert TOTAL_STEPS == 12

"""Integration test: verify the full installer chain works end-to-end."""

import sys
from pathlib import Path


def test_dependencies_parsing():
    """The real dependencies.json should parse with our Pydantic models."""
    from src.config import load_dependencies

    deps = load_dependencies(Path("scripts/dependencies.json"))
    assert deps.repositories.comfyui.url.startswith("https://")
    assert "torch" in deps.pip_packages.torch.packages
    assert len(deps.pip_packages.wheels) >= 1
    assert len(deps.pip_packages.standard) >= 5
    assert deps.files.comfy_settings is not None


def test_platform_detection():
    """Platform factory should return WindowsPlatform on Windows."""
    from src.platform.base import get_platform

    p = get_platform()
    assert p.__class__.__name__ == "WindowsPlatform"


def test_python_detection():
    """Should detect our current Python."""
    from src.platform.base import get_platform

    p = get_platform()
    # We're running Python 3.14, so looking for 3.13 may fail,
    # but the method should return None gracefully (not crash)
    major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    result = p.detect_python(major_minor)
    assert result is not None, f"Could not detect Python {major_minor}"
    assert result.exists()


def test_git_available():
    """Git should be detected."""
    from src.utils.commands import check_command_exists, get_command_version

    assert check_command_exists("git")
    ver = get_command_version("git")
    assert ver is not None
    assert "git version" in ver


def test_installer_modules_import():
    """All installer modules should import without errors."""
    from src.installer.phase1 import run_phase1, install_aria2, check_prerequisites
    from src.installer.phase2 import (
        run_phase2, clone_comfyui, setup_junction_architecture,
        install_core_dependencies, install_custom_nodes,
    )
    from src.installer.updater import run_update, update_comfyui_core


def test_check_prerequisites():
    """check_prerequisites should run without crashing."""
    from src.installer.phase1 import check_prerequisites
    from src.utils.logging import setup_logger

    log = setup_logger(total_steps=1)
    result = check_prerequisites(log)
    assert isinstance(result, bool)

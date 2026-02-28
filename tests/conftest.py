"""Shared pytest fixtures for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_log_file(tmp_path: Path) -> Path:
    """Provide a temporary log file path."""
    return tmp_path / "test_log.txt"


@pytest.fixture
def tmp_config_file(tmp_path: Path) -> Path:
    """Provide a temporary config file path."""
    return tmp_path / "local-config.json"


@pytest.fixture
def sample_dependencies_json(tmp_path: Path) -> Path:
    """Create a minimal dependencies.json for testing."""
    import json

    data = {
        "repositories": {
            "comfyui": {"url": "https://github.com/comfyanonymous/ComfyUI.git"},
            "workflows": {"url": "https://github.com/UmeAiRT/ComfyUI-Workflows"},
        },
        "tools": {
            "vs_build_tools": {
                "install_path": "C:\\Program Files\\Test\\BuildTools",
                "url": "https://example.com/vs_buildtools.exe",
                "arguments": "--quiet",
            }
        },
        "pip_packages": {
            "upgrade": ["pip", "wheel"],
            "torch": {
                "packages": "torch torchvision",
                "index_url": "https://download.pytorch.org/whl/cu130",
            },
            "comfyui_requirements": "requirements.txt",
            "wheels": [
                {
                    "name": "test-package-1.0-cp313-win_amd64",
                    "url": "https://example.com/test.whl",
                }
            ],
            "standard": ["numpy", "pillow"],
            "git_repos": [],
        },
        "files": {
            "comfy_settings": {
                "url": "https://example.com/settings.json",
                "destination": "user/default/comfy.settings.json",
            }
        },
    }

    path = tmp_path / "dependencies.json"
    with open(path, "w") as f:
        json.dump(data, f)

    return path

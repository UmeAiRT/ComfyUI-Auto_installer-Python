"""Tests for the updater module."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from src.enums import InstallerFatalError

if TYPE_CHECKING:
    from pathlib import Path


class TestDetectPython:
    """Tests for _detect_python."""

    def test_detects_venv_python(self, tmp_path: Path) -> None:
        """Should detect Python in a venv if install_type file says 'venv'."""
        from src.installer.updater import _detect_python

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "install_type").write_text("venv", encoding="utf-8")

        # Create fake venv python
        import sys
        if sys.platform == "win32":
            venv_py = scripts_dir / "venv" / "Scripts" / "python.exe"
        else:
            venv_py = scripts_dir / "venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.touch()

        log = MagicMock()
        result = _detect_python(scripts_dir, log)
        assert result == venv_py

    def test_missing_install_type_raises(self, tmp_path: Path) -> None:
        """Should raise InstallerFatalError if install_type file is missing."""
        from src.installer.updater import _detect_python

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()

        log = MagicMock()
        with pytest.raises(InstallerFatalError):
            _detect_python(scripts_dir, log)

    def test_venv_python_missing_raises(self, tmp_path: Path) -> None:
        """Should raise InstallerFatalError if install_type says venv but python is missing."""
        from src.installer.updater import _detect_python

        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "install_type").write_text("venv", encoding="utf-8")
        # Don't create the venv python

        log = MagicMock()
        with pytest.raises(InstallerFatalError):
            _detect_python(scripts_dir, log)


class TestMergeNodeManifests:
    """Tests for _merge_node_manifests."""

    def test_first_install_copies(self, tmp_path: Path) -> None:
        """When dest doesn't exist, source is copied as-is."""
        from src.installer.updater import _merge_node_manifests

        source = tmp_path / "source.json"
        dest = tmp_path / "dest.json"
        source_data = {"nodes": [
            {"name": "NodeA", "url": "https://a.git", "tier": "minimal"},
            {"name": "NodeB", "url": "https://b.git", "tier": "full"},
        ]}
        source.write_text(json.dumps(source_data), encoding="utf-8")

        log = MagicMock()
        added = _merge_node_manifests(source, dest, log)

        assert added == 2
        assert dest.exists()
        result = json.loads(dest.read_text(encoding="utf-8"))
        assert len(result["nodes"]) == 2

    def test_adds_new_nodes(self, tmp_path: Path) -> None:
        """Should add nodes from source that are not in dest."""
        from src.installer.updater import _merge_node_manifests

        source = tmp_path / "source.json"
        dest = tmp_path / "dest.json"

        source.write_text(json.dumps({"nodes": [
            {"name": "NodeA", "url": "https://a.git"},
            {"name": "NodeB", "url": "https://b.git"},
            {"name": "NodeC", "url": "https://c.git"},
        ]}), encoding="utf-8")

        dest.write_text(json.dumps({"nodes": [
            {"name": "NodeA", "url": "https://a.git"},
        ]}), encoding="utf-8")

        log = MagicMock()
        added = _merge_node_manifests(source, dest, log)

        assert added == 2
        result = json.loads(dest.read_text(encoding="utf-8"))
        names = [n["name"] for n in result["nodes"]]
        assert "NodeA" in names
        assert "NodeB" in names
        assert "NodeC" in names

    def test_preserves_user_changes(self, tmp_path: Path) -> None:
        """Should not overwrite existing nodes (user may have changed tier)."""
        from src.installer.updater import _merge_node_manifests

        source = tmp_path / "source.json"
        dest = tmp_path / "dest.json"

        source.write_text(json.dumps({"nodes": [
            {"name": "NodeA", "url": "https://a.git", "tier": "full"},
        ]}), encoding="utf-8")

        # User changed tier to minimal
        dest.write_text(json.dumps({"nodes": [
            {"name": "NodeA", "url": "https://a.git", "tier": "minimal"},
        ]}), encoding="utf-8")

        log = MagicMock()
        added = _merge_node_manifests(source, dest, log)

        assert added == 0
        result = json.loads(dest.read_text(encoding="utf-8"))
        # User's tier change should be preserved
        assert result["nodes"][0]["tier"] == "minimal"

    def test_no_changes_no_write(self, tmp_path: Path) -> None:
        """When there are no new nodes, dest file should not be rewritten."""
        from src.installer.updater import _merge_node_manifests

        source = tmp_path / "source.json"
        dest = tmp_path / "dest.json"

        data = {"nodes": [{"name": "NodeA", "url": "https://a.git"}]}
        source.write_text(json.dumps(data), encoding="utf-8")
        dest.write_text(json.dumps(data), encoding="utf-8")

        # Record modification time
        mtime_before = dest.stat().st_mtime

        log = MagicMock()
        added = _merge_node_manifests(source, dest, log)

        assert added == 0
        # File should not have been rewritten
        assert dest.stat().st_mtime == mtime_before


class TestUpdateDependencies:
    """Tests for update_dependencies (previously untested)."""

    def test_skips_when_no_deps_file(self, tmp_path: Path) -> None:
        """Should skip gracefully when dependencies.json is absent."""
        from src.installer.updater import update_dependencies

        log = MagicMock()
        python_exe = tmp_path / "python.exe"
        comfy_path = tmp_path / "ComfyUI"
        install_path = tmp_path / "install"
        install_path.mkdir()
        # No scripts/dependencies.json

        update_dependencies(python_exe, comfy_path, install_path, log)
        log.warning.assert_called_once()

    def test_torch_update_uses_get_torch(self, tmp_path: Path) -> None:
        """Should use get_torch(cuda_tag) instead of direct .torch access."""
        from src.installer.updater import update_dependencies

        log = MagicMock()
        python_exe = tmp_path / "python.exe"
        comfy_path = tmp_path / "ComfyUI"
        install_path = tmp_path / "install"
        scripts_dir = install_path / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create a minimal deps file with multi-CUDA torch config (the case that crashed)
        import json
        deps_data = {
            "repositories": {"comfyui": {"url": "https://example.com"}},
            "pip_packages": {
                "comfyui_requirements": "requirements.txt",
                "torch": {
                    "cu130": {"packages": "torch torchvision", "index_url": "https://torch.url/cu130"},
                    "cu128": {"packages": "torch torchvision", "index_url": "https://torch.url/cu128"},
                },
                "packages": [],
            },
        }
        (scripts_dir / "dependencies.json").write_text(json.dumps(deps_data), encoding="utf-8")

        # Mock all external calls
        with (
            patch("src.installer.updater.confirm", return_value=True),
            patch("src.installer.updater.uv_install") as mock_uv,
            patch("src.installer.optimizations._get_cuda_version_from_torch", return_value=None),
        ):
            # This call would crash before the fix with:
            # AttributeError: 'dict' object has no attribute 'packages'
            update_dependencies(python_exe, comfy_path, install_path, log)

        # Should have called uv_install for torch with the fallback tag
        torch_calls = [c for c in mock_uv.call_args_list if c[0][1] and "torch" in c[0][1]]
        assert len(torch_calls) >= 1


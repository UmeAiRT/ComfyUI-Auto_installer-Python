"""Tests for the configuration system."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.config import (
    DependenciesConfig,
    InstallerSettings,
    load_dependencies,
    load_settings,
    save_settings,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestInstallerSettings:
    """Tests for user-local settings."""

    def test_defaults(self) -> None:
        """Default settings have secure values."""
        settings = InstallerSettings()
        assert settings.listen_address == "127.0.0.1"  # NOT 0.0.0.0
        assert settings.listen_port == 8188
        assert settings.install_type == "venv"
        assert settings.package_manager == "uv"
        assert settings.use_sage_attention is True
        assert settings.gh_user == "UmeAiRT"

    def test_load_missing_file(self, tmp_config_file: Path) -> None:
        """Loading a missing file returns defaults."""
        settings = load_settings(tmp_config_file)
        assert settings.listen_address == "127.0.0.1"

    def test_save_and_load(self, tmp_config_file: Path) -> None:
        """Settings round-trip through JSON."""
        original = InstallerSettings(
            listen_address="192.168.1.100",
            listen_port=9090,
            gh_user="MyFork",
        )
        save_settings(original, tmp_config_file)

        loaded = load_settings(tmp_config_file)
        assert loaded.listen_address == "192.168.1.100"
        assert loaded.listen_port == 9090
        assert loaded.gh_user == "MyFork"
        # Other fields should keep defaults
        assert loaded.install_type == "venv"

    def test_partial_json(self, tmp_config_file: Path) -> None:
        """Loading a JSON with only some fields uses defaults for the rest."""
        data = {"listen_port": 7777}
        with open(tmp_config_file, "w") as f:
            json.dump(data, f)

        settings = load_settings(tmp_config_file)
        assert settings.listen_port == 7777
        assert settings.listen_address == "127.0.0.1"  # default


class TestDependenciesConfig:
    """Tests for dependencies.json loading."""

    def test_load_valid(self, sample_dependencies_json: Path) -> None:
        """Loading a valid dependencies.json succeeds."""
        config = load_dependencies(sample_dependencies_json)
        assert config.repositories.comfyui.url == "https://github.com/comfyanonymous/ComfyUI.git"
        assert config.pip_packages.torch.index_url == "https://download.pytorch.org/whl/cu130"
        assert len(config.pip_packages.wheels) == 1
        assert config.pip_packages.wheels[0].name == "test-package-1.0-cp313-win_amd64"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Loading a missing file raises FileNotFoundError."""
        import pytest

        with pytest.raises(FileNotFoundError):
            load_dependencies(tmp_path / "nonexistent.json")

    def test_defaults(self) -> None:
        """DependenciesConfig has sensible defaults when created empty."""
        config = DependenciesConfig()
        assert config.repositories.comfyui.url == "https://github.com/comfyanonymous/ComfyUI.git"
        assert config.pip_packages.upgrade == ["pip", "wheel"]


class TestDependenciesValidation:
    """Tests for dependencies.json validation edge cases."""

    def test_empty_json(self, tmp_path: Path) -> None:
        """Loading an empty JSON object uses all defaults."""
        path = tmp_path / "empty.json"
        with open(path, "w") as f:
            json.dump({}, f)

        config = load_dependencies(path)
        assert config.repositories.comfyui.url == "https://github.com/comfyanonymous/ComfyUI.git"

    def test_extra_fields_ignored(self, tmp_path: Path) -> None:
        """Unknown fields in JSON are silently ignored."""
        path = tmp_path / "extra.json"
        with open(path, "w") as f:
            json.dump({"unknown_field": "value", "pip_packages": {"upgrade": ["pip"]}}, f)

        config = load_dependencies(path)
        assert config.pip_packages.upgrade == ["pip"]


class TestToolConfigSha256:
    """Tests for ToolConfig SHA-256 fields."""

    def test_sha256_default_empty(self) -> None:
        """ToolConfig sha256 defaults to empty string."""
        from src.config import ToolConfig
        tool = ToolConfig(url="https://example.com/tool.exe")
        assert tool.sha256 == ""

    def test_sha256_set(self) -> None:
        """ToolConfig stores SHA-256."""
        from src.config import ToolConfig
        tool = ToolConfig(url="https://example.com/tool.exe", sha256="abc123")
        assert tool.sha256 == "abc123"


class TestWheelConfigChecksums:
    """Tests for WheelConfig SHA-256 checksums."""

    def test_checksums_default_empty(self) -> None:
        """WheelConfig checksums dict defaults to empty."""
        from src.config import WheelConfig
        whl = WheelConfig(name="pkg", versions={"cp313": "https://example.com/pkg.whl"})
        assert whl.checksums == {}

    def test_resolve_returns_3_tuple_with_checksum(self) -> None:
        """resolve() returns (name, url, sha256) when checksum exists."""
        from src.config import WheelConfig
        whl = WheelConfig(
            name="pkg",
            versions={"cp313": "https://example.com/pkg.whl"},
            checksums={"cp313": "deadbeef"},
        )
        result = whl.resolve((3, 13))
        assert result == ("pkg", "https://example.com/pkg.whl", "deadbeef")

    def test_resolve_cuda_tag_exact_match(self) -> None:
        """resolve() uses {platform}_{cuda}_{cpython} composite tag when available."""
        from unittest.mock import patch

        from src.config import WheelConfig
        whl = WheelConfig(
            name="pkg",
            versions={"linux_cu130_cp313": "https://example.com/pkg-linux-cu130.whl"},
            checksums={"linux_cu130_cp313": "deadbeef"},
        )
        with patch("sys.platform", "linux"):
            result = whl.resolve((3, 13), cuda_tag="cu130")
        assert result == ("pkg-linux-cu130", "https://example.com/pkg-linux-cu130.whl", "deadbeef")

    def test_resolve_cuda_tag_fallback(self) -> None:
        """resolve() falls back to OS-agnostic then {cpython} if explicit tags provided but not in dict."""
        from src.config import WheelConfig
        whl = WheelConfig(
            name="pkg",
            versions={"cp313": "https://example.com/pkg-any.whl"},
            checksums={"cp313": "beef"},
        )
        from unittest.mock import patch
        with patch("sys.platform", "linux"):
            result = whl.resolve((3, 13), cuda_tag="cu130")
        assert result == ("pkg-any", "https://example.com/pkg-any.whl", "beef")

    def test_resolve_returns_none_checksum_when_missing(self) -> None:
        """resolve() returns None for sha256 when no checksum entry."""
        from src.config import WheelConfig
        whl = WheelConfig(
            name="pkg",
            versions={"cp313": "https://example.com/pkg.whl"},
        )
        result = whl.resolve((3, 13))
        assert result == ("pkg", "https://example.com/pkg.whl", None)

    def test_resolve_returns_none_for_missing_version(self) -> None:
        """resolve() returns None if version not in versions."""
        from src.config import WheelConfig
        whl = WheelConfig(
            name="pkg",
            versions={"cp313": "https://example.com/pkg.whl"},
        )
        assert whl.resolve((3, 11)) is None


class TestPipPackagesGetTorch:
    """Tests for multi-CUDA PyTorch selection."""

    def test_get_torch_from_dict(self) -> None:
        """get_torch() retrieves the correct config from a multi-CUDA dict."""
        from src.config import PipPackages, TorchConfig
        pkgs = PipPackages(torch={
            "cu130": TorchConfig(index_url="url/cu130"),
            "cu128": TorchConfig(index_url="url/cu128")
        })
        assert pkgs.get_torch("cu130").index_url == "url/cu130"
        assert pkgs.get_torch("cu128").index_url == "url/cu128"
        assert pkgs.get_torch("cu118") is None

    def test_get_torch_legacy(self) -> None:
        """get_torch() falls back to returning the single TorchConfig if dict format not used."""
        from src.config import PipPackages, TorchConfig
        cfg = TorchConfig(index_url="url/legacy")
        pkgs = PipPackages(torch=cfg)
        assert pkgs.get_torch("cu130").index_url == "url/legacy"
        assert pkgs.get_torch("cu128").index_url == "url/legacy"

    def test_supported_cuda_tags(self) -> None:
        from src.config import PipPackages, TorchConfig
        pkgs = PipPackages(torch={
            "cu130": TorchConfig(index_url="url/cu130"),
            "cu128": TorchConfig(index_url="url/cu128")
        })
        assert set(pkgs.supported_cuda_tags) == {"cu130", "cu128"}


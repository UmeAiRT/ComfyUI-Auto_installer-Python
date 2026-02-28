"""Tests for the unified model downloader engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.downloader.engine import (
    ModelBundle,
    ModelCatalog,
    ModelFile,
    ModelVariant,
    BundleMeta,
    load_catalog,
    resolve_file_path,
    PATH_TYPE_MAP,
)


@pytest.fixture
def sample_catalog_json(tmp_path: Path) -> Path:
    """Create a minimal catalog JSON for testing."""
    data = {
        "TEST_MODEL": {
            "_meta": {
                "base_url": "https://example.com/models",
                "loader_type": "test",
                "clip_type": "test"
            },
            "fp16": {
                "min_vram": 24,
                "files": [
                    {
                        "url": "/diffusion_models/FLUX/model-fp16.safetensors",
                        "path_type": "flux_diff",
                        "filename": "model-fp16.safetensors"
                    },
                    {
                        "url": "/clip/clip_l.safetensors",
                        "path_type": "clip",
                        "filename": "clip_l.safetensors"
                    }
                ]
            },
            "GGUF_Q4": {
                "min_vram": 8,
                "files": [
                    {
                        "url": "/unet/FLUX/model-Q4_K_S.gguf",
                        "path_type": "flux_unet",
                        "filename": "model-Q4_K_S.gguf"
                    }
                ]
            }
        },
        "EMPTY_MODEL": {
            "_meta": {
                "base_url": "https://example.com/models",
                "loader_type": "empty"
            }
        }
    }
    path = tmp_path / "test_catalog.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class TestLoadCatalog:
    """Tests for catalog loading."""

    def test_load_valid(self, sample_catalog_json: Path) -> None:
        catalog = load_catalog(sample_catalog_json)
        assert "TEST_MODEL" in catalog.bundles
        assert "EMPTY_MODEL" in catalog.bundles

    def test_bundle_meta(self, sample_catalog_json: Path) -> None:
        catalog = load_catalog(sample_catalog_json)
        bundle = catalog.bundles["TEST_MODEL"]
        assert bundle.meta.base_url == "https://example.com/models"
        assert bundle.meta.loader_type == "test"

    def test_variants_parsed(self, sample_catalog_json: Path) -> None:
        catalog = load_catalog(sample_catalog_json)
        bundle = catalog.bundles["TEST_MODEL"]
        assert "fp16" in bundle.variants
        assert "GGUF_Q4" in bundle.variants
        assert bundle.variants["fp16"].min_vram == 24
        assert bundle.variants["GGUF_Q4"].min_vram == 8

    def test_files_parsed(self, sample_catalog_json: Path) -> None:
        catalog = load_catalog(sample_catalog_json)
        variant = catalog.bundles["TEST_MODEL"].variants["fp16"]
        assert len(variant.files) == 2
        assert variant.files[0].path_type == "flux_diff"
        assert variant.files[0].filename == "model-fp16.safetensors"
        assert variant.files[1].path_type == "clip"

    def test_empty_bundle(self, sample_catalog_json: Path) -> None:
        catalog = load_catalog(sample_catalog_json)
        bundle = catalog.bundles["EMPTY_MODEL"]
        assert len(bundle.variants) == 0

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_catalog(tmp_path / "nonexistent.json")


class TestResolveFilePath:
    """Tests for path_type → directory resolution."""

    def test_known_path_types(self, tmp_path: Path) -> None:
        """All registered path types resolve correctly."""
        for path_type, expected_subdir in PATH_TYPE_MAP.items():
            result = resolve_file_path(tmp_path, path_type, "test.bin")
            assert result == tmp_path / expected_subdir / "test.bin"

    def test_unknown_path_type(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown path_type"):
            resolve_file_path(tmp_path, "nonexistent_type", "test.bin")

    def test_flux_diff(self, tmp_path: Path) -> None:
        result = resolve_file_path(tmp_path, "flux_diff", "model.safetensors")
        assert result == tmp_path / "diffusion_models" / "FLUX" / "model.safetensors"

    def test_clip(self, tmp_path: Path) -> None:
        result = resolve_file_path(tmp_path, "clip", "t5xxl.safetensors")
        assert result == tmp_path / "clip" / "t5xxl.safetensors"

    def test_vae(self, tmp_path: Path) -> None:
        result = resolve_file_path(tmp_path, "vae", "ae.safetensors")
        assert result == tmp_path / "vae" / "ae.safetensors"


class TestModelFileUrl:
    """Tests for URL construction."""

    def test_relative_url(self) -> None:
        """Relative URLs are prefixed with base_url."""
        bundle = ModelBundle(
            meta=BundleMeta(base_url="https://example.com/models"),
            variants={
                "fp16": ModelVariant(
                    min_vram=24,
                    files=[ModelFile(url="/clip/test.bin", path_type="clip", filename="test.bin")]
                )
            }
        )
        file_entry = bundle.variants["fp16"].files[0]
        url = bundle.meta.base_url.rstrip("/") + file_entry.url
        assert url == "https://example.com/models/clip/test.bin"

    def test_absolute_url(self) -> None:
        """Absolute URLs are used as-is."""
        file_entry = ModelFile(
            url="https://cdn.example.com/file.bin",
            path_type="clip",
            filename="file.bin"
        )
        assert file_entry.url.startswith("http")

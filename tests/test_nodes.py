"""Tests for the custom nodes manifest engine."""

import json
from pathlib import Path

import pytest

from src.installer.nodes import VALID_TIERS, filter_by_tier, load_manifest


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    """Create a minimal test manifest."""
    data = {
        "_meta": {"version": 3},
        "nodes": [
            {
                "name": "TestNode-A",
                "url": "https://github.com/test/TestNode-A.git",
                "tier": "minimal",
                "requirements": "requirements.txt",
                "note": "Essential node",
            },
            {
                "name": "TestNode-B",
                "url": "https://github.com/test/TestNode-B.git",
                "tier": "umeairt",
            },
            {
                "name": "TestNode-C",
                "url": "https://github.com/test/TestNode-C.git",
                "tier": "full",
            },
            {
                "name": "TestNode-Sub",
                "url": "https://github.com/test/TestNode-Sub.git",
                "subfolder": "TestNode-A/subpack",
                "requirements": "requirements.txt",
            },
        ],
    }
    path = tmp_path / "custom_nodes.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestLoadManifest:
    def test_load_valid(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        assert len(manifest.nodes) == 4

    def test_node_fields(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        node_a = manifest.nodes[0]
        assert node_a.name == "TestNode-A"
        assert node_a.tier == "minimal"
        assert node_a.requirements == "requirements.txt"
        assert node_a.note == "Essential node"

    def test_node_defaults(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        node_sub = manifest.nodes[3]
        assert node_sub.tier == "full"
        assert node_sub.note is None

    def test_subfolder_node(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        node_sub = manifest.nodes[3]
        assert node_sub.subfolder == "TestNode-A/subpack"

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "nonexistent.json")

    def test_empty_manifest(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text('{"nodes": []}', encoding="utf-8")
        manifest = load_manifest(path)
        assert len(manifest.nodes) == 0


class TestFilterByTier:
    """Test tier-based filtering."""

    def test_minimal_tier(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        filtered = filter_by_tier(manifest, "minimal")
        names = [n.name for n in filtered.nodes]
        assert names == ["TestNode-A"]

    def test_umeairt_tier(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        filtered = filter_by_tier(manifest, "umeairt")
        names = [n.name for n in filtered.nodes]
        assert "TestNode-A" in names
        assert "TestNode-B" in names
        assert "TestNode-C" not in names

    def test_full_tier(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        filtered = filter_by_tier(manifest, "full")
        assert len(filtered.nodes) == 4

    def test_invalid_tier_defaults_to_full(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        filtered = filter_by_tier(manifest, "nonexistent")
        assert len(filtered.nodes) == 4


class TestLoadRealManifest:
    """Test against the actual custom_nodes.json in the project."""

    def test_real_manifest_loads(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        assert len(manifest.nodes) >= 30

    def test_real_manifest_has_tier_nodes(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        minimal = filter_by_tier(manifest, "minimal")
        umeairt = filter_by_tier(manifest, "umeairt")
        assert len(minimal.nodes) >= 1  # At least ComfyUI-Manager
        assert len(umeairt.nodes) >= 5  # Manager + Sync + Toolkit + Crystools + nunchaku

    def test_real_manifest_all_have_urls(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        for node in manifest.nodes:
            assert node.url.startswith("https://"), f"{node.name} has invalid URL"

    def test_real_manifest_all_have_valid_tiers(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        for node in manifest.nodes:
            assert node.tier in VALID_TIERS, f"{node.name} has invalid tier: {node.tier}"

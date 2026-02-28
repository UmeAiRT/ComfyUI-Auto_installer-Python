"""Tests for the custom nodes manifest engine."""

import json
from pathlib import Path

import pytest

from src.installer.nodes import NodeEntry, NodeManifest, load_manifest


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    """Create a minimal test manifest."""
    data = {
        "_meta": {"version": 2},
        "nodes": [
            {
                "name": "TestNode-A",
                "url": "https://github.com/test/TestNode-A.git",
                "required": True,
                "requirements": "requirements.txt",
                "note": "Essential node",
            },
            {
                "name": "TestNode-B",
                "url": "https://github.com/test/TestNode-B.git",
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
        assert len(manifest.nodes) == 3

    def test_node_fields(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        node_a = manifest.nodes[0]
        assert node_a.name == "TestNode-A"
        assert node_a.required is True
        assert node_a.requirements == "requirements.txt"
        assert node_a.note == "Essential node"

    def test_node_defaults(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        node_b = manifest.nodes[1]
        assert node_b.required is False
        assert node_b.requirements is None
        assert node_b.subfolder is None
        assert node_b.note is None

    def test_subfolder_node(self, manifest_file: Path):
        manifest = load_manifest(manifest_file)
        node_sub = manifest.nodes[2]
        assert node_sub.subfolder == "TestNode-A/subpack"

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "nonexistent.json")

    def test_empty_manifest(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text('{"nodes": []}', encoding="utf-8")
        manifest = load_manifest(path)
        assert len(manifest.nodes) == 0


class TestLoadRealManifest:
    """Test against the actual custom_nodes.json in the project."""

    def test_real_manifest_loads(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        assert len(manifest.nodes) >= 30

    def test_real_manifest_has_required_nodes(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        required = [n for n in manifest.nodes if n.required]
        assert len(required) >= 2  # Manager + UmeAiRT-Sync

    def test_real_manifest_all_have_urls(self):
        real_path = Path("scripts/custom_nodes.json")
        if not real_path.exists():
            pytest.skip("Real manifest not available")
        manifest = load_manifest(real_path)
        for node in manifest.nodes:
            assert node.url.startswith("https://"), f"{node.name} has invalid URL"

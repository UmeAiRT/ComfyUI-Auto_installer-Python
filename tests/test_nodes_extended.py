"""Tests for custom node management — install_node, update_node, install_all_nodes, update_all_nodes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from src.installer.nodes import (
    NodeEntry,
    NodeManifest,
    filter_by_tier,
    install_all_nodes,
    install_node,
    load_manifest,
    update_all_nodes,
    update_node,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestInstallNode:
    """Tests for install_node."""

    def test_already_installed(self, tmp_path: Path) -> None:
        """Should skip if node directory already exists."""
        node = NodeEntry(name="TestNode", url="https://example.com/test.git", tier="full")
        nodes_dir = tmp_path / "custom_nodes"
        (nodes_dir / "TestNode").mkdir(parents=True)

        log = MagicMock()
        assert install_node(node, nodes_dir, MagicMock(), log) is True
        log.sub.assert_called_once()
        assert "already installed" in log.sub.call_args[0][0]

    def test_clone_success(self, tmp_path: Path) -> None:
        """Should clone and return True on success."""
        node = NodeEntry(name="NewNode", url="https://example.com/new.git", tier="full")
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        log = MagicMock()
        with patch("src.installer.nodes.run_and_log") as mock_run:
            assert install_node(node, nodes_dir, MagicMock(), log) is True
            mock_run.assert_called_once()

    def test_clone_failure_retries(self, tmp_path: Path) -> None:
        """Should retry 3 times then return False."""
        from src.utils.commands import CommandError

        node = NodeEntry(name="BadNode", url="https://example.com/bad.git", tier="full")
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        log = MagicMock()
        with patch(
            "src.installer.nodes.run_and_log",
            side_effect=CommandError("git", 128, "error"),
        ):
            assert install_node(node, nodes_dir, MagicMock(), log) is False

    def test_installs_requirements(self, tmp_path: Path) -> None:
        """Should install requirements.txt after cloning."""
        node = NodeEntry(
            name="ReqNode",
            url="https://example.com/req.git",
            tier="full",
            requirements="requirements.txt",
        )
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        # Simulate clone creating the directory with requirements
        def fake_clone(*args, **kwargs):
            node_dir = nodes_dir / "ReqNode"
            node_dir.mkdir(exist_ok=True)
            (node_dir / "requirements.txt").write_text("numpy\n")

        log = MagicMock()
        with (
            patch("src.installer.nodes.run_and_log", side_effect=fake_clone),
            patch("src.installer.nodes.uv_install") as mock_uv,
        ):
            assert install_node(node, nodes_dir, MagicMock(), log) is True
            mock_uv.assert_called_once()

    def test_subfolder_node(self, tmp_path: Path) -> None:
        """Should use subfolder path instead of node name."""
        node = NodeEntry(
            name="SubNode",
            url="https://example.com/sub.git",
            tier="full",
            subfolder="ParentNode/SubNode",
        )
        nodes_dir = tmp_path / "custom_nodes"
        (nodes_dir / "ParentNode" / "SubNode").mkdir(parents=True)

        log = MagicMock()
        assert install_node(node, nodes_dir, MagicMock(), log) is True


class TestUpdateNode:
    """Tests for update_node."""

    def test_not_installed_delegates_to_install(self, tmp_path: Path) -> None:
        """Should install if node doesn't exist."""
        node = NodeEntry(name="NewNode", url="https://example.com/new.git", tier="full")
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        log = MagicMock()
        with patch("src.installer.nodes.run_and_log"):
            assert update_node(node, nodes_dir, MagicMock(), log) is True

    def test_pulls_existing_node(self, tmp_path: Path) -> None:
        """Should git pull --ff-only on existing node."""
        node = NodeEntry(name="ExistNode", url="https://example.com/exist.git", tier="full")
        nodes_dir = tmp_path / "custom_nodes"
        (nodes_dir / "ExistNode").mkdir(parents=True)

        log = MagicMock()
        with patch("src.installer.nodes.run_and_log") as mock_run:
            assert update_node(node, nodes_dir, MagicMock(), log) is True
            git_args = mock_run.call_args[0][1]
            assert "--ff-only" in git_args

    def test_pull_failure_continues(self, tmp_path: Path) -> None:
        """Should warn but return True if pull fails (local changes)."""
        from src.utils.commands import CommandError

        node = NodeEntry(name="DirtyNode", url="https://example.com/dirty.git", tier="full")
        nodes_dir = tmp_path / "custom_nodes"
        (nodes_dir / "DirtyNode").mkdir(parents=True)

        log = MagicMock()
        with patch(
            "src.installer.nodes.run_and_log",
            side_effect=CommandError("git", 1, "diverged"),
        ):
            assert update_node(node, nodes_dir, MagicMock(), log) is True
            log.sub.assert_any_call("  DirtyNode: pull failed (may have local changes)", style="yellow")


class TestInstallAllNodes:
    """Tests for install_all_nodes."""

    def test_counts_success_and_failure(self, tmp_path: Path) -> None:
        """Should count successes and failures."""
        nodes = [
            NodeEntry(name="Good1", url="https://g1.git", tier="full"),
            NodeEntry(name="Bad1", url="https://bad.git", tier="full"),
            NodeEntry(name="Good2", url="https://g2.git", tier="full"),
        ]
        manifest = NodeManifest(nodes=nodes)
        nodes_dir = tmp_path / "custom_nodes"

        log = MagicMock()

        def side_effect(node, *args, **kwargs):
            return node.name != "Bad1"

        with patch("src.installer.nodes.install_node", side_effect=side_effect):
            success, fail = install_all_nodes(manifest, nodes_dir, MagicMock(), log)
            assert success == 2
            assert fail == 1


class TestUpdateAllNodes:
    """Tests for update_all_nodes."""

    def test_preserves_user_nodes(self, tmp_path: Path) -> None:
        """User-installed nodes should be listed but not touched."""
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()
        # User-installed node (not in manifest)
        (nodes_dir / "UserCustomNode").mkdir()
        # Bundled node (in manifest)
        (nodes_dir / "BundledNode").mkdir()

        manifest = NodeManifest(
            nodes=[NodeEntry(name="BundledNode", url="https://b.git", tier="full")]
        )

        log = MagicMock()
        with patch("src.installer.nodes.update_node", return_value=True):
            success, fail = update_all_nodes(manifest, nodes_dir, MagicMock(), log)
            assert success == 1
            assert fail == 0

        # Should have logged user nodes
        log.item.assert_any_call("1 user-installed node(s) preserved:", style="success")


class TestLoadManifest:
    """Tests for load_manifest."""

    def test_loads_valid_manifest(self, tmp_path: Path) -> None:
        """Should parse a valid manifest file."""
        data = {"nodes": [
            {"name": "NodeA", "url": "https://a.git", "tier": "minimal"},
            {"name": "NodeB", "url": "https://b.git", "tier": "full"},
        ]}
        path = tmp_path / "custom_nodes.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        manifest = load_manifest(path)
        assert len(manifest.nodes) == 2
        assert manifest.nodes[0].name == "NodeA"


class TestFilterByTier:
    """Tests for filter_by_tier."""

    def test_minimal_tier(self) -> None:
        manifest = NodeManifest(nodes=[
            NodeEntry(name="A", url="https://a.git", tier="minimal"),
            NodeEntry(name="B", url="https://b.git", tier="umeairt"),
            NodeEntry(name="C", url="https://c.git", tier="full"),
        ])
        result = filter_by_tier(manifest, "minimal")
        assert len(result.nodes) == 1
        assert result.nodes[0].name == "A"

    def test_full_tier_includes_all(self) -> None:
        manifest = NodeManifest(nodes=[
            NodeEntry(name="A", url="https://a.git", tier="minimal"),
            NodeEntry(name="B", url="https://b.git", tier="umeairt"),
            NodeEntry(name="C", url="https://c.git", tier="full"),
        ])
        result = filter_by_tier(manifest, "full")
        assert len(result.nodes) == 3

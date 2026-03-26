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
    reinstall_all_node_requirements,
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

    def test_reinstalls_user_node_requirements(self, tmp_path: Path) -> None:
        """User-installed nodes with requirements.txt should have deps reinstalled."""
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()
        # User-installed node with requirements
        user_node = nodes_dir / "MyCustomNode"
        user_node.mkdir()
        (user_node / "requirements.txt").write_text("some-package>=1.0\n")

        manifest = NodeManifest(nodes=[])  # Empty manifest

        log = MagicMock()
        python_exe = MagicMock()
        with patch("src.installer.nodes.uv_install") as mock_uv:
            update_all_nodes(manifest, nodes_dir, python_exe, log)
            mock_uv.assert_called_once()


class TestReinstallAllNodeRequirements:
    """Tests for reinstall_all_node_requirements."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Should return (0, 0) if custom_nodes doesn't exist."""
        log = MagicMock()
        installed, skipped = reinstall_all_node_requirements(
            tmp_path / "nonexistent", MagicMock(), log
        )
        assert installed == 0
        assert skipped == 0

    def test_installs_requirements_for_all_nodes(self, tmp_path: Path) -> None:
        """Should find and install requirements for all nodes."""
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        # Node with requirements.txt
        node_a = nodes_dir / "NodeA"
        node_a.mkdir()
        (node_a / "requirements.txt").write_text("numpy\n")

        # Node with requirements-no-cupy.txt
        node_b = nodes_dir / "NodeB"
        node_b.mkdir()
        (node_b / "requirements-no-cupy.txt").write_text("scipy\n")

        # Node without requirements
        node_c = nodes_dir / "NodeC"
        node_c.mkdir()

        log = MagicMock()
        with patch("src.installer.nodes.uv_install") as mock_uv:
            installed, skipped = reinstall_all_node_requirements(
                nodes_dir, MagicMock(), log
            )
            assert installed == 2
            assert skipped == 1
            assert mock_uv.call_count == 2

    def test_skips_hidden_and_pycache(self, tmp_path: Path) -> None:
        """Should skip hidden directories and __pycache__."""
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        (nodes_dir / ".hidden").mkdir()
        (nodes_dir / ".hidden" / "requirements.txt").write_text("x\n")
        (nodes_dir / "__pycache__").mkdir()

        # Only real node
        real = nodes_dir / "RealNode"
        real.mkdir()
        (real / "requirements.txt").write_text("y\n")

        log = MagicMock()
        with patch("src.installer.nodes.uv_install") as mock_uv:
            installed, skipped = reinstall_all_node_requirements(
                nodes_dir, MagicMock(), log
            )
            assert installed == 1
            assert skipped == 0
            assert mock_uv.call_count == 1

    def test_prefers_requirements_txt_over_no_cupy(self, tmp_path: Path) -> None:
        """When both requirements files exist, should use requirements.txt."""
        nodes_dir = tmp_path / "custom_nodes"
        nodes_dir.mkdir()

        node = nodes_dir / "DualNode"
        node.mkdir()
        (node / "requirements.txt").write_text("main\n")
        (node / "requirements-no-cupy.txt").write_text("fallback\n")

        log = MagicMock()
        with patch("src.installer.nodes.uv_install") as mock_uv:
            installed, _ = reinstall_all_node_requirements(
                nodes_dir, MagicMock(), log
            )
            assert installed == 1
            # Should have been called with requirements.txt, not requirements-no-cupy.txt
            req_path = mock_uv.call_args.kwargs.get("requirements")
            assert req_path is not None
            assert req_path.name == "requirements.txt"


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

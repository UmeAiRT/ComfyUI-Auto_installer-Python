"""
Custom nodes management — additive-only manifest system.

Replaces ComfyUI-Manager snapshots with a simple, reliable engine:
- Install missing bundled nodes (git clone)
- Update existing bundled nodes (git pull)
- Never remove user-installed nodes

Uses uv for pip installs when available (10-100x faster).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.utils.commands import CommandError, check_command_exists, run_and_log
from src.utils.logging import InstallerLogger, get_logger


class NodeEntry(BaseModel):
    """A custom node definition in the manifest."""

    name: str
    url: str
    required: bool = False
    requirements: str | None = None
    subfolder: str | None = None
    note: str | None = None


class NodeManifest(BaseModel):
    """The custom_nodes.json manifest."""

    nodes: list[NodeEntry] = Field(default_factory=list)


def load_manifest(path: Path) -> NodeManifest:
    """Load and validate the custom_nodes.json manifest."""
    if not path.exists():
        raise FileNotFoundError(f"Node manifest not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return NodeManifest.model_validate(data)


def _pip_install_requirements(
    python_exe: Path,
    req_file: Path,
    log: InstallerLogger,
) -> None:
    """
    Install requirements using uv (fast) or pip (fallback).

    Args:
        python_exe: Path to the Python executable.
        req_file: Path to requirements.txt file.
        log: Logger.
    """
    if check_command_exists("uv"):
        run_and_log(
            "uv", ["pip", "install", "-r", str(req_file),
                    "--python", str(python_exe)],
            ignore_errors=True,
            timeout=300,
        )
    else:
        run_and_log(
            str(python_exe),
            ["-m", "pip", "install", "-r", str(req_file)],
            ignore_errors=True,
            timeout=300,
        )


def install_node(
    node: NodeEntry,
    custom_nodes_dir: Path,
    python_exe: Path,
    log: InstallerLogger,
) -> bool:
    """
    Install a single custom node (git clone + pip install requirements).

    Args:
        node: The node entry from the manifest.
        custom_nodes_dir: ComfyUI/custom_nodes directory.
        python_exe: Python executable for pip installs.
        log: Logger.

    Returns:
        True if installed successfully.
    """
    # Handle subfolder nodes (e.g. Impact-Subpack inside Impact-Pack)
    if node.subfolder:
        node_dir = custom_nodes_dir / node.subfolder
    else:
        node_dir = custom_nodes_dir / node.name

    if node_dir.exists():
        log.sub(f"  {node.name}: already installed", style="success")
        return True

    # Clone with retry (network can be flaky)
    log.sub(f"  {node.name}: cloning...", style="cyan")
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            clone_args = ["clone", node.url, str(node_dir)]
            if attempt > 1:
                # Shallow clone on retry to reduce data
                clone_args = ["clone", "--depth", "1", node.url, str(node_dir)]
                log.sub(f"  {node.name}: retry {attempt}/{max_retries} (shallow)...", style="yellow")
            run_and_log("git", clone_args, timeout=300)
            break  # Success
        except CommandError as e:
            # Clean up partial clone before retry
            if node_dir.exists():
                import shutil
                shutil.rmtree(node_dir, ignore_errors=True)
            if attempt == max_retries:
                log.sub(f"  {node.name}: clone FAILED after {max_retries} attempts ({e})", style="red")
                return False

    # Install requirements
    if node.requirements:
        req_file = node_dir / node.requirements
        if req_file.exists():
            _pip_install_requirements(python_exe, req_file, log)

    return True


def update_node(
    node: NodeEntry,
    custom_nodes_dir: Path,
    python_exe: Path,
    log: InstallerLogger,
) -> bool:
    """
    Update an existing custom node (git pull + pip install requirements).

    Returns True if updated, False if not found or failed.
    """
    if node.subfolder:
        node_dir = custom_nodes_dir / node.subfolder
    else:
        node_dir = custom_nodes_dir / node.name

    if not node_dir.exists():
        # Not installed — install it
        return install_node(node, custom_nodes_dir, python_exe, log)

    # Git pull
    log.sub(f"  {node.name}: updating...", style="cyan")
    try:
        run_and_log(
            "git", ["-C", str(node_dir), "pull", "--ff-only"],
            ignore_errors=True,
            timeout=60,
        )
    except CommandError:
        log.sub(f"  {node.name}: pull failed (may have local changes)", style="yellow")

    # Re-install requirements (in case they changed)
    if node.requirements:
        req_file = node_dir / node.requirements
        if req_file.exists():
            _pip_install_requirements(python_exe, req_file, log)

    return True


def install_all_nodes(
    manifest: NodeManifest,
    custom_nodes_dir: Path,
    python_exe: Path,
    log: InstallerLogger,
) -> tuple[int, int]:
    """
    Install all nodes from the manifest.

    Only installs missing nodes — existing nodes and user-installed
    nodes are left untouched.

    Returns:
        (success_count, fail_count)
    """
    log.step("Installing Custom Nodes")
    log.item(f"{len(manifest.nodes)} nodes in manifest")

    custom_nodes_dir.mkdir(parents=True, exist_ok=True)
    success = 0
    fail = 0

    # Install required nodes first
    required = [n for n in manifest.nodes if n.required]
    optional = [n for n in manifest.nodes if not n.required]

    for node in required + optional:
        if install_node(node, custom_nodes_dir, python_exe, log):
            success += 1
        else:
            fail += 1

    log.item(f"Nodes: {success} OK, {fail} failed", style="success" if fail == 0 else "yellow")
    return success, fail


def update_all_nodes(
    manifest: NodeManifest,
    custom_nodes_dir: Path,
    python_exe: Path,
    log: InstallerLogger,
) -> tuple[int, int]:
    """
    Update all bundled nodes. User-installed nodes are NEVER touched.

    Returns:
        (success_count, fail_count)
    """
    log.step("Updating Custom Nodes")

    # List all directories in custom_nodes
    installed_names = {d.name for d in custom_nodes_dir.iterdir() if d.is_dir()} if custom_nodes_dir.exists() else set()
    manifest_names = {n.name for n in manifest.nodes}

    # User-installed nodes = installed but not in manifest
    user_nodes = installed_names - manifest_names
    if user_nodes:
        log.item(f"{len(user_nodes)} user-installed node(s) preserved:", style="success")
        for name in sorted(user_nodes):
            log.sub(f"  {name}", style="dim")

    # Update bundled nodes
    log.item(f"Updating {len(manifest.nodes)} bundled nodes...")
    success = 0
    fail = 0

    for node in manifest.nodes:
        if update_node(node, custom_nodes_dir, python_exe, log):
            success += 1
        else:
            fail += 1

    log.item(f"Updated: {success} OK, {fail} failed", style="success" if fail == 0 else "yellow")
    return success, fail

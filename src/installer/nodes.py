"""
Custom nodes management — additive-only manifest system.

Provides a simple, reliable engine for managing ComfyUI custom nodes:

- **Install** missing bundled nodes (``git clone``).
- **Update** existing bundled nodes (``git pull --ff-only``).
- **Never** remove user-installed nodes.

Uses ``uv`` exclusively for package installs.

The manifest is defined in ``custom_nodes.json`` with the schema
described by :class:`NodeManifest` and :class:`NodeEntry`.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.enums import NodeTier
from src.utils.commands import CommandError, run_and_log
from src.utils.packaging import uv_install

if TYPE_CHECKING:
    from pathlib import Path

    from src.utils.logging import InstallerLogger


# Tier hierarchy — each tier includes all nodes from lower tiers.
TIER_HIERARCHY: dict[NodeTier, set[NodeTier]] = {
    NodeTier.MINIMAL: {NodeTier.MINIMAL},
    NodeTier.UMEAIRT: {NodeTier.MINIMAL, NodeTier.UMEAIRT},
    NodeTier.FULL: {NodeTier.MINIMAL, NodeTier.UMEAIRT, NodeTier.FULL},
}

VALID_TIERS = list(TIER_HIERARCHY.keys())


class NodeEntry(BaseModel):
    """A single custom node definition in the manifest.

    Attributes:
        name: Directory name for the node (used as clone target).
        url: Git repository URL.
        tier: Bundle tier — ``"minimal"``, ``"umeairt"``, or
            ``"full"`` (default).  Hierarchical: each tier includes
            nodes from all lower tiers.
        requirements: Relative path to a ``requirements.txt`` inside
            the cloned directory (e.g. ``"requirements.txt"``).
        subfolder: If set, the node lives inside another node's
            directory (e.g. Impact-Subpack inside Impact-Pack).
        note: Human-readable comment (not used by the installer).
    """

    name: str
    url: str
    tier: str = "full"
    requirements: str | None = None
    subfolder: str | None = None
    note: str | None = None

    # v2 compat — ignored if tier is set
    required: bool = False


class NodeManifest(BaseModel):
    """The custom_nodes.json manifest."""

    nodes: list[NodeEntry] = Field(default_factory=list)


def filter_by_tier(manifest: NodeManifest, tier: str) -> NodeManifest:
    """Return a new manifest containing only nodes for the given tier.

    Each tier includes all nodes from lower tiers::

        minimal ⊂ umeairt ⊂ full

    Args:
        manifest: The full manifest.
        tier: One of ``"minimal"``, ``"umeairt"``, ``"full"``.

    Returns:
        A filtered NodeManifest.
    """
    try:
        tier_key = NodeTier(tier) if isinstance(tier, str) else tier
    except ValueError:
        tier_key = NodeTier.FULL
    allowed = TIER_HIERARCHY.get(tier_key, TIER_HIERARCHY[NodeTier.FULL])
    filtered = [n for n in manifest.nodes if n.tier in allowed]
    return NodeManifest(nodes=filtered)


def load_manifest(path: Path) -> NodeManifest:
    """Load and validate the ``custom_nodes.json`` manifest.

    Args:
        path: Absolute path to the JSON manifest file.

    Returns:
        Validated :class:`NodeManifest` instance.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
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
    Install requirements via uv.

    Args:
        python_exe: Path to the Python executable.
        req_file: Path to requirements.txt file.
        log: Logger.
    """

    try:
        uv_install(
            python_exe,
            requirements=req_file,
            ignore_errors=True,
            timeout=900,  # 15 minutes for heavy nodes like Impact-Pack
        )
    except CommandError as e:
        log.error(f"Failed to install requirements for {req_file.parent.name}: {e}")


def install_node(
    node: NodeEntry,
    custom_nodes_dir: Path,
    python_exe: Path,
    log: InstallerLogger,
) -> bool:
    """Install a single custom node via ``git clone``.

    Clones the repository into ``custom_nodes_dir/node.name``
    (or ``node.subfolder`` if specified). On network failure,
    retries up to 3 times with shallow clone.

    After cloning, installs pip requirements if ``node.requirements``
    is set.

    Args:
        node: Node definition from the manifest.
        custom_nodes_dir: ``ComfyUI/custom_nodes/`` directory.
        python_exe: Path to the venv Python executable.
        log: Installer logger for user-facing messages.

    Returns:
        ``True`` if the node was installed (or already existed).
    """
    # Handle subfolder nodes (e.g. Impact-Subpack inside Impact-Pack)
    node_dir = custom_nodes_dir / node.subfolder if node.subfolder else custom_nodes_dir / node.name

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
    """Update an existing custom node via ``git pull --ff-only``.

    If the node is not installed, delegates to :func:`install_node`.
    Re-installs pip requirements after pulling in case they changed.

    Args:
        node: Node definition from the manifest.
        custom_nodes_dir: ``ComfyUI/custom_nodes/`` directory.
        python_exe: Path to the venv Python executable.
        log: Installer logger for user-facing messages.

    Returns:
        ``True`` if updated successfully.
    """
    node_dir = custom_nodes_dir / node.subfolder if node.subfolder else custom_nodes_dir / node.name

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
    """Install all nodes from the manifest (additive-only).

    Only installs missing nodes — existing nodes and user-installed
    nodes are left untouched. Required nodes are processed first.

    Args:
        manifest: Validated node manifest.
        custom_nodes_dir: ``ComfyUI/custom_nodes/`` directory.
        python_exe: Path to the venv Python executable.
        log: Installer logger for user-facing messages.

    Returns:
        Tuple of ``(success_count, fail_count)``.
    """
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
    """Update all bundled nodes. User-installed nodes are NEVER touched.

    Identifies user-installed nodes (present on disk but not in
    the manifest) and preserves them. Then updates each manifest
    node via :func:`update_node`.

    Args:
        manifest: Validated node manifest.
        custom_nodes_dir: ``ComfyUI/custom_nodes/`` directory.
        python_exe: Path to the venv Python executable.
        log: Installer logger for user-facing messages.

    Returns:
        Tuple of ``(success_count, fail_count)``.
    """
    log.step("Updating Custom Nodes")

    # List all directories in custom_nodes (ignore __pycache__ and hidden dirs)
    installed_names = {
        d.name for d in custom_nodes_dir.iterdir()
        if d.is_dir() and d.name != "__pycache__" and not d.name.startswith(".")
    } if custom_nodes_dir.exists() else set()
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

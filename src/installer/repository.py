"""
ComfyUI repository setup — Steps 5-6.

Clones the ComfyUI repository and sets up the "wireless"
external-folder architecture using junctions (Windows) or
symlinks (Linux/macOS). This keeps user data (models, outputs,
custom nodes) outside the Git repo for painless updates.

Typical usage::

    setup_git_config(log)
    clone_comfyui(install_path, comfy_path, deps, log)
    setup_junction_architecture(install_path, comfy_path, log)
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from src.enums import InstallerFatalError
from src.platform.base import get_platform
from src.utils.commands import CommandError, run_and_log

if TYPE_CHECKING:
    from pathlib import Path

    from src.config import DependenciesConfig
    from src.utils.logging import InstallerLogger

# Folders managed by the junction architecture
EXTERNAL_FOLDERS = ["custom_nodes", "models", "output", "input", "user"]


def setup_git_config(log: InstallerLogger) -> None:
    """Enable ``core.longpaths`` globally in Git.

    Required on Windows to handle deep node_modules-style paths
    inside custom nodes.

    Args:
        log: Installer logger for user-facing messages.
    """
    log.item("Configuring Git for long paths...")
    try:
        run_and_log("git", ["config", "--global", "core.longpaths", "true"], ignore_errors=True)
        log.sub("Git long paths configured.", style="success")
    except CommandError:
        log.warning("Could not set git config (might need admin).", level=2)


def clone_comfyui(
    install_path: Path,
    comfy_path: Path,
    deps: DependenciesConfig,
    log: InstallerLogger,
    *,
    max_retries: int = 3,
) -> None:
    """Clone the ComfyUI repository from the URL in *deps*.

    Skips cloning if ``comfy_path`` already exists. Retries up to
    *max_retries* times on failure (network errors, timeouts).

    Args:
        install_path: Root installation directory.
        comfy_path: Target path for the clone (``install_path/ComfyUI``).
        deps: Parsed ``dependencies.json`` containing the repo URL.
        log: Installer logger for user-facing messages.
        max_retries: Number of clone attempts before giving up.

    Raises:
        SystemExit: If cloning fails after all retries.
    """
    if comfy_path.exists():
        log.sub("ComfyUI directory already exists.", style="success")
        return

    repo_url = deps.repositories.comfyui.url
    log.item(f"Cloning from {repo_url}...")

    for attempt in range(1, max_retries + 1):
        try:
            run_and_log("git", ["clone", repo_url, str(comfy_path)])
            if comfy_path.exists():
                log.sub("ComfyUI cloned successfully.", style="success")
                return
        except CommandError:
            pass

        # Clean up partial clone before retry
        if comfy_path.exists():
            shutil.rmtree(comfy_path, ignore_errors=True)

        if attempt < max_retries:
            log.warning(f"Clone attempt {attempt}/{max_retries} failed, retrying...", level=2)
        else:
            log.error(f"ComfyUI cloning failed after {max_retries} attempts!")
            raise InstallerFatalError(f"ComfyUI cloning failed after {max_retries} attempts!")


def setup_junction_architecture(
    install_path: Path,
    comfy_path: Path,
    log: InstallerLogger,
) -> None:
    """Create the external-folder architecture with junctions/symlinks.

    For each folder in ``EXTERNAL_FOLDERS``:

    * **Case 1** — Internal dir exists, no external: move to external.
    * **Case 2** — Both exist: merge internal into external, delete internal.
    * **Case 3** — Neither exists: create external.

    Then creates a junction (Windows) or symlink (Linux) from the
    internal path to the external directory.

    Args:
        install_path: Root installation directory containing external folders.
        comfy_path: ComfyUI repository directory.
        log: Installer logger for user-facing messages.
    """
    platform = get_platform()

    for folder in EXTERNAL_FOLDERS:
        external_path = install_path / folder
        internal_path = comfy_path / folder

        if internal_path.exists() and not platform.is_link(internal_path):
            # Real directory from git clone exists
            if not external_path.exists():
                # Case 1: Move default structure to external
                log.item(f"Moving '{folder}' to external location...")
                shutil.move(str(internal_path), str(external_path))
            else:
                # Case 2: External exists (previous install) — merge, then delete internal
                log.item(f"External '{folder}' detected. Merging default structure...")
                shutil.copytree(str(internal_path), str(external_path), dirs_exist_ok=True)
                shutil.rmtree(str(internal_path))
        elif not external_path.exists():
            # Case 3: Neither exist — create external
            external_path.mkdir(parents=True, exist_ok=True)

        # Create junction/symlink
        if not internal_path.exists():
            platform.create_link(internal_path, external_path)

"""
Unified installation orchestrator.

Single entry point for the complete ComfyUI installation.  All logic
lives in domain modules; this file only coordinates the 12-step flow.

Steps:

=====  ================================  ===================================
Step   Label                             Module
=====  ================================  ===================================
1      System Configuration              :mod:`.system`
2      Checking Prerequisites            :mod:`.system`
3      Creating Python Environment        :mod:`.environment`
4      Provisioning Configuration         :mod:`.environment`
5      Setting Up ComfyUI                :mod:`.repository`
6      External Folders                  :mod:`.repository`
7      Core Dependencies                 :mod:`.dependencies`
8      Python Packages                   :mod:`.dependencies`
9      Custom Nodes                      :mod:`.dependencies`
10     Performance Optimizations          :mod:`.optimizations`
11     Finalization                       :mod:`.finalize`
12     Model Downloads                   :mod:`.finalize`
=====  ================================  ===================================

Error handling convention
-------------------------

Each module follows one of three strategies:

**Fatal** — ``SystemExit(1)`` or re-raise.  Used when the step is
blocking and the installation cannot continue (e.g. Git missing,
venv creation failure, ComfyUI clone failure after retries).

**Log + continue** — Log a warning and return ``False`` or ``None``.
Used for non-critical enhancements that should not block the
installation (e.g. aria2 missing → fallback to httpx,
optimization packages failing, individual custom node clone failure).

**Best-effort** — ``subprocess.run`` with return code silently
ignored.  Used only for truly optional side-effects
(e.g. ``conda init``).  Always annotated with
``# best-effort, ignore errors``.

All ``subprocess.run()`` calls without ``check=True`` are annotated
with one of these conventions for quick auditability.

Typical usage::

    from src.installer.install import run_install
    run_install(install_path=Path("D:/ComfyUI"))
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from src import __version__
from src.config import load_dependencies, load_settings
from src.enums import InstallerFatalError, InstallType, NodeTier
from src.installer.dependencies import (
    install_core_dependencies,
    install_custom_nodes,
    install_python_packages,
    install_wheels,
)
from src.installer.environment import provision_scripts, setup_environment
from src.installer.finalize import (
    create_launchers,
    install_cli_in_environment,
    install_comfy_settings,
    offer_model_downloads,
)
from src.installer.optimizations import install_optimizations
from src.installer.repository import clone_comfyui, setup_git_config, setup_junction_architecture
from src.installer.system import check_prerequisites, ensure_aria2, install_git
from src.platform.base import get_platform
from src.utils.logging import setup_logger
from src.utils.prompts import confirm

if TYPE_CHECKING:
    from src.utils.logging import InstallerLogger

TOTAL_STEPS = 12


def run_install(
    install_path: Path,
    install_type: InstallType = InstallType.VENV,
    *,
    verbose: bool = False,
    node_tier: NodeTier = NodeTier.FULL,
    cuda_version: str = "",
    skip_nodes: bool = False,
) -> None:
    """Run the complete ComfyUI installation in 12 unified steps.

    Resolves *install_path* to an absolute path, initialises the
    logger, then executes each step sequentially.  Any fatal
    failure raises :class:`~src.enums.InstallerFatalError`.

    Args:
        install_path: Root installation directory. Will be
            resolved to an absolute path.
        install_type: Environment type — :attr:`InstallType.VENV`
            (default) or :attr:`InstallType.CONDA`.
        verbose: If ``True``, show full subprocess output during
            installs and git clones.
        node_tier: Custom nodes bundle tier —
            :attr:`NodeTier.MINIMAL`, :attr:`NodeTier.UMEAIRT`,
            or :attr:`NodeTier.FULL` (default).

    Raises:
        InstallerFatalError: On missing prerequisites or fatal errors.
    """
    # Resolve to absolute path
    install_path = install_path.resolve()

    log = setup_logger(
        log_file=install_path / "logs" / "install_log.txt",
        total_steps=TOTAL_STEPS,
        verbose=verbose,
    )
    log.banner("UmeAiRT", "ComfyUI — Auto-Installer", __version__)

    # ── Detect previous failed installation ───────────────────────
    marker = install_path / ".install_in_progress"
    _handle_partial_install(install_path, marker, log)

    # Create marker — removed only on successful completion
    install_path.mkdir(parents=True, exist_ok=True)
    marker.write_text("started", encoding="utf-8")

    # ── Load user settings ────────────────────────────────────────
    load_settings(install_path / "scripts" / "local-config.json")

    # ── Step 1: System Configuration ──────────────────────────────
    log.step("System Configuration")
    platform = get_platform()
    platform.enable_long_paths()

    # ── Step 2: Checking Prerequisites ────────────────────────────
    log.step("Checking Prerequisites")

    # Load source dependencies early for tool URLs
    from src.installer.environment import find_source_scripts
    source_dir = find_source_scripts()
    source_deps_file = source_dir / "dependencies.json" if source_dir else None
    if source_deps_file and source_deps_file.exists():
        source_deps = load_dependencies(source_deps_file)
        git_url = source_deps.tools.git_windows.url
        git_sha256 = source_deps.tools.git_windows.sha256
        aria2_url = source_deps.tools.aria2_windows.url
        aria2_sha256 = source_deps.tools.aria2_windows.sha256
    else:
        git_url = ""
        git_sha256 = ""
        aria2_url = ""
        aria2_sha256 = ""

    if not check_prerequisites(log):
        kwargs: dict[str, str] = {}
        if git_url:
            kwargs["git_url"] = git_url
        if git_sha256:
            kwargs["git_sha256"] = git_sha256
        if not install_git(log, **kwargs):
            raise InstallerFatalError("Git is required but could not be installed.")

    ensure_aria2(install_path, log, aria2_url=aria2_url, aria2_sha256=aria2_sha256)

    # ── Step 3: Creating Python Environment ───────────────────────
    log.step("Creating Python Environment")
    python_exe = setup_environment(install_path, install_type, log)

    # ── Step 4: Provisioning Configuration ────────────────────────
    log.step("Provisioning Configuration")
    provision_scripts(install_path, log)

    # Save the installation type for launchers and tools
    scripts_dir = install_path / "scripts"
    (scripts_dir / "install_type").write_text(install_type.value, encoding="utf-8")

    # ── Load dependencies for remaining steps ─────────────────────
    comfy_path = install_path / "ComfyUI"
    deps_file = scripts_dir / "dependencies.json"

    if not deps_file.exists():
        log.error(f"dependencies.json not found at {deps_file}")
        raise InstallerFatalError(f"dependencies.json not found at {deps_file}")

    deps = load_dependencies(deps_file)

    # Set UTF-8 environment
    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"

    # ── Step 5: Setting Up ComfyUI ────────────────────────────────
    log.step("Setting Up ComfyUI")
    setup_git_config(log)
    clone_comfyui(install_path, comfy_path, deps, log)

    # ── Step 6: External Folders ──────────────────────────────────
    log.step("External Folders Architecture")
    setup_junction_architecture(install_path, comfy_path, log)

    # ── Step 6b: GPU Detection & Selection ────────────────────────────
    from src.installer.gpu_setup import detect_and_select_gpu

    cuda_tag = detect_and_select_gpu(platform, deps, log, cuda_override=cuda_version)

    # ── Step 7: Core Dependencies ─────────────────────────────────
    log.step("Core Dependencies")
    install_core_dependencies(python_exe, comfy_path, deps, log, cuda_tag=cuda_tag)  # type: ignore

    # ── Step 8: Python Packages ───────────────────────────────────
    log.step("Installing Python Packages")
    install_python_packages(python_exe, deps, log)
    install_wheels(python_exe, install_path, deps, log, cuda_tag=cuda_tag)  # type: ignore

    # ── Step 9: Custom Nodes ──────────────────────────────────────────
    if skip_nodes:
        log.step(f"Custom Nodes ({node_tier})")
        log.sub("Skipped (--skip-nodes). Nodes will be installed at runtime.", style="cyan")
    else:
        log.step(f"Custom Nodes ({node_tier})")
        install_custom_nodes(python_exe, comfy_path, install_path, log, node_tier=node_tier, source_dir=source_dir)

    # ── Step 10: Performance Optimizations ────────────────────────
    if skip_nodes:
        log.step("Performance Optimizations")
        log.sub("Skipped (--skip-nodes). Optimizations will be applied at runtime.", style="cyan")
    else:
        log.step("Performance Optimizations")
        install_optimizations(python_exe, comfy_path, install_path, deps, log)

    # ── Step 11: Finalization ─────────────────────────────────────
    log.step("Finalization")
    install_cli_in_environment(python_exe, log)
    install_comfy_settings(install_path, log, source_dir=source_dir)
    create_launchers(install_path, log, cuda_tag=cuda_tag)

    # ── Step 12: Model Downloads ──────────────────────────────────
    log.step("Model Downloads")
    offer_model_downloads(install_path, log, source_dir=source_dir)

    # ── Done ──────────────────────────────────────────────────────
    marker.unlink(missing_ok=True)

    # Installation summary table
    from rich.table import Table

    summary = Table(title="Installation Summary", show_header=False, border_style="green")
    summary.add_column("Key", style="bold")
    summary.add_column("Value")
    summary.add_row("Install Path", str(install_path))
    summary.add_row("Environment", install_type.value)
    summary.add_row("Node Tier", node_tier.value)
    summary.add_row("CUDA", cuda_tag)
    summary.add_row("Python", str(python_exe))
    summary.add_row("Platform", platform.name)
    from src.utils.logging import console
    console.print(summary)

    log.success("Installation Complete!", level=0)
    log.success("ComfyUI and all components have been installed.", level=1)
    log.item("Double-click UmeAiRT-Start-ComfyUI to launch!")


def _handle_partial_install(
    install_path: Path,
    marker: Path,
    log: InstallerLogger,
) -> None:
    """Detect and handle a previously failed installation.

    If a ``.install_in_progress`` marker file exists, a previous run
    crashed before completing.  Offer the user two choices:

    1. **Clean up** — delete the partial install directory and start fresh.
    2. **Continue** — keep existing files and retry from step 1.

    Args:
        install_path: Root installation directory.
        marker: Path to the marker file.
        log: Installer logger.
    """
    if not marker.exists():
        return

    log.warning(
        "A previous installation was interrupted before completing.",
        level=1,
    )
    log.item(f"Location: {install_path}")

    if confirm("Delete the partial installation and start fresh?"):
        log.item("Cleaning up partial installation...")
        # Preserve the logs directory for debugging
        logs_dir = install_path / "logs"
        logs_backup = None
        if logs_dir.exists():
            import tempfile

            logs_backup = Path(tempfile.mkdtemp()) / "logs"
            shutil.copytree(logs_dir, logs_backup)

        # Remove everything in install_path
        for child in install_path.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

        # Restore logs
        if logs_backup and logs_backup.exists():
            shutil.copytree(logs_backup, logs_dir)
            shutil.rmtree(logs_backup, ignore_errors=True)

        log.sub("Partial installation removed.", style="success")
    else:
        log.item("Keeping existing files. Retrying installation...")
        marker.unlink(missing_ok=True)


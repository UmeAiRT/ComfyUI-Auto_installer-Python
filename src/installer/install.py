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

Typical usage::

    from src.installer.install import run_install
    run_install(install_path=Path("D:/ComfyUI"))
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from src import __version__
from src.config import load_dependencies, load_settings
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
from src.utils.download import set_install_path
from src.utils.logging import setup_logger

if TYPE_CHECKING:
    from pathlib import Path

TOTAL_STEPS = 12


def run_install(
    install_path: Path,
    install_type: str = "venv",
    *,
    verbose: bool = False,
    node_tier: str = "full",
) -> None:
    """Run the complete ComfyUI installation in 12 unified steps.

    Resolves *install_path* to an absolute path, initialises the
    logger, then executes each step sequentially.  Any fatal
    failure raises ``SystemExit(1)``.

    Args:
        install_path: Root installation directory. Will be
            resolved to an absolute path.
        install_type: Environment type — ``"venv"`` (default) or
            ``"conda"`` (not yet implemented).
        verbose: If ``True``, show full subprocess output during
            installs and git clones.
        node_tier: Custom nodes bundle tier — ``"minimal"``,
            ``"umeairt"``, or ``"full"`` (default).

    Raises:
        SystemExit: On missing prerequisites or fatal errors.
    """
    # Resolve to absolute path
    install_path = install_path.resolve()

    log = setup_logger(
        log_file=install_path / "logs" / "install_log.txt",
        total_steps=TOTAL_STEPS,
        verbose=verbose,
    )
    log.banner("UmeAiRT", "ComfyUI — Auto-Installer", __version__)

    # ── Load user settings ────────────────────────────────────────
    load_settings(install_path / "scripts" / "local-config.json")

    # ── Step 1: System Configuration ──────────────────────────────
    log.step("System Configuration")
    platform = get_platform()
    platform.enable_long_paths()

    # ── Step 2: Checking Prerequisites ────────────────────────────
    log.step("Checking Prerequisites")
    set_install_path(install_path)

    if not check_prerequisites(log) and not install_git(log):
        raise SystemExit(1)

    ensure_aria2(install_path, log)

    # ── Step 3: Creating Python Environment ───────────────────────
    log.step("Creating Python Environment")
    python_exe = setup_environment(install_path, install_type, log)

    # ── Step 4: Provisioning Configuration ────────────────────────
    log.step("Provisioning Configuration")
    provision_scripts(install_path, log)

    # Save the installation type for launchers and tools
    scripts_dir = install_path / "scripts"
    (scripts_dir / "install_type").write_text(install_type, encoding="utf-8")

    # ── Load dependencies for remaining steps ─────────────────────
    comfy_path = install_path / "ComfyUI"
    deps_file = scripts_dir / "dependencies.json"

    if not deps_file.exists():
        log.error(f"dependencies.json not found at {deps_file}")
        raise SystemExit(1)

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

    # ── Step 7: Core Dependencies ─────────────────────────────────
    log.step("Core Dependencies")
    install_core_dependencies(python_exe, comfy_path, deps, log)

    # ── Step 8: Python Packages ───────────────────────────────────
    log.step("Installing Python Packages")
    install_python_packages(python_exe, deps, log)
    install_wheels(python_exe, install_path, deps, log)

    # ── Step 9: Custom Nodes ──────────────────────────────────────────
    log.step(f"Custom Nodes ({node_tier})")
    install_custom_nodes(python_exe, comfy_path, install_path, log, node_tier=node_tier)

    # ── Step 10: Performance Optimizations ────────────────────────
    log.step("Performance Optimizations")
    install_optimizations(python_exe, comfy_path, install_path, deps, log)

    # ── Step 11: Finalization ─────────────────────────────────────
    log.step("Finalization")
    install_cli_in_environment(python_exe, log)
    install_comfy_settings(install_path, log)
    create_launchers(install_path, log)

    # ── Step 12: Model Downloads ──────────────────────────────────
    log.step("Model Downloads")
    offer_model_downloads(install_path, log)

    # ── Done ──────────────────────────────────────────────────────
    log.success("Installation Complete!", level=0)
    log.success("ComfyUI and all components have been installed.", level=1)
    log.item("Double-click UmeAiRT-Start-ComfyUI to launch!")


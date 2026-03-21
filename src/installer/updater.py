"""
ComfyUI Update System.

Migrated to uv — no raw pip.
Handles:
- ComfyUI core update (git pull)
- Custom nodes update via manifest
- Python dependencies update
- Triton / SageAttention re-install
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src import __version__
from src.config import load_dependencies
from src.utils.commands import CommandError, run_and_log
from src.utils.logging import InstallerLogger, setup_logger
from src.utils.packaging import uv_install
from src.utils.prompts import confirm

if TYPE_CHECKING:
    from pathlib import Path


def update_comfyui_core(comfy_path: Path, log: InstallerLogger) -> None:
    """Update ComfyUI core via git pull."""
    log.step("Updating ComfyUI Core")

    if not comfy_path.exists():
        log.error("ComfyUI directory not found!")
        return

    log.item("Pulling latest changes...")
    try:
        run_and_log("git", ["-C", str(comfy_path), "pull", "--ff-only"])
        log.sub("ComfyUI updated.", style="success")
    except CommandError:
        log.warning("Git pull failed. You may have local changes.", level=2)
        log.info("Try: git -C ComfyUI stash && git -C ComfyUI pull")


def update_custom_nodes(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Update bundled custom nodes. User-installed nodes are NEVER touched.

    Merges new nodes from the source manifest (additive-only) so that
    user customizations are preserved while newly added nodes are
    picked up on every update.
    """

    from src.installer.environment import find_source_scripts
    from src.installer.nodes import load_manifest, update_all_nodes

    scripts_dir = install_path / "scripts"
    manifest_path = scripts_dir / "custom_nodes.json"

    # Merge new nodes from source (additive-only — never overwrites user changes)
    source_dir = find_source_scripts()
    if source_dir:
        source_manifest = source_dir / "custom_nodes.json"
        if source_manifest.exists():
            scripts_dir.mkdir(parents=True, exist_ok=True)
            added = _merge_node_manifests(source_manifest, manifest_path, log)
            if added > 0:
                log.item(f"custom_nodes.json: {added} new node(s) added from source.", style="cyan")
            else:
                log.sub("custom_nodes.json is up to date.", style="success")

    if not manifest_path.exists():
        log.warning("custom_nodes.json not found. Skipping node updates.", level=1)
        return

    custom_nodes_dir = comfy_path / "custom_nodes"
    manifest = load_manifest(manifest_path)
    update_all_nodes(manifest, custom_nodes_dir, python_exe, log)


def update_dependencies(
    python_exe: Path,
    comfy_path: Path,
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Update Python dependencies via uv."""
    log.step("Updating Python Dependencies")

    deps_file = install_path / "scripts" / "dependencies.json"
    if not deps_file.exists():
        log.warning("dependencies.json not found. Skipping.", level=1)
        return

    deps = load_dependencies(deps_file)

    # Update ComfyUI requirements
    req_file = comfy_path / deps.pip_packages.comfyui_requirements
    if req_file.exists():
        log.item("Updating ComfyUI requirements...")
        uv_install(python_exe, requirements=req_file, upgrade=True)

    # Update torch
    if confirm("Update PyTorch? (Only if there's a new CUDA version)"):
        torch_pkgs = deps.pip_packages.torch.packages.split()
        log.item("Updating PyTorch...")
        uv_install(
            python_exe,
            torch_pkgs,
            index_url=deps.pip_packages.torch.index_url,
            upgrade=True,
        )


def run_update(install_path: Path, *, verbose: bool = False) -> None:
    """
    Run the full update process.

    Args:
        install_path: Root installation directory.
        verbose: Show detailed subprocess output.
    """
    log = setup_logger(
        log_file=install_path / "logs" / "update_log.txt",
        total_steps=5,
        verbose=verbose,
    )
    log.banner("UmeAiRT", "ComfyUI — Updater", __version__)

    comfy_path = install_path / "ComfyUI"
    scripts_dir = install_path / "scripts"

    # Detect python executable
    python_exe = _detect_python(scripts_dir, log)

    # Run update steps
    update_comfyui_core(comfy_path, log)
    update_custom_nodes(python_exe, comfy_path, install_path, log)
    update_dependencies(python_exe, comfy_path, install_path, log)

    # Model security scan (non-blocking)
    _scan_models_warning(install_path, log)

    log.step("Update Complete!")
    log.success("All components have been updated.", level=1)


def _merge_node_manifests(
    source_path: Path,
    dest_path: Path,
    log: InstallerLogger,
) -> int:
    """Merge source manifest into dest (additive-only).

    New nodes (by name) are appended. Existing nodes are never
    modified or removed, preserving user customizations.

    If *dest_path* does not exist, the source is copied as-is.

    Args:
        source_path: Path to the upstream manifest.
        dest_path: Path to the installed manifest (may not exist).
        log: Installer logger.

    Returns:
        Number of new nodes added.
    """
    import json
    import shutil

    if not dest_path.exists():
        shutil.copy2(source_path, dest_path)
        # Count nodes in the source for reporting
        with open(source_path, encoding="utf-8") as f:
            data = json.load(f)
        return len(data.get("nodes", []))

    with open(source_path, encoding="utf-8") as f:
        src_data = json.load(f)
    with open(dest_path, encoding="utf-8") as f:
        dst_data = json.load(f)

    existing_names = {n["name"] for n in dst_data.get("nodes", [])}
    new_nodes = [n for n in src_data.get("nodes", []) if n["name"] not in existing_names]

    if new_nodes:
        dst_data.setdefault("nodes", []).extend(new_nodes)
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(dst_data, f, indent=2, ensure_ascii=False)

    return len(new_nodes)


def _detect_python(scripts_dir: Path, log: InstallerLogger) -> Path:
    """Detect the Python executable from the install type."""
    import sys

    install_type_file = scripts_dir / "install_type"

    if install_type_file.exists():
        install_type = install_type_file.read_text().strip()

        if install_type == "venv":
            if sys.platform == "win32":
                venv_py = scripts_dir / "venv" / "Scripts" / "python.exe"
            else:
                venv_py = scripts_dir / "venv" / "bin" / "python"

            if venv_py.exists():
                log.item(f"Venv Python detected: {venv_py}", style="cyan")
                return venv_py

        elif install_type == "conda":
            conda_env = scripts_dir / "conda_env"
            if sys.platform == "win32":
                conda_py = conda_env / "python.exe"
            else:
                conda_py = conda_env / "bin" / "python"

            if conda_py.exists():
                log.item(f"Conda Python detected: {conda_py}", style="cyan")
                return conda_py

    log.error("Could not determine venv Python. Is this a valid installation?")
    log.item("Expected 'install_type' file in scripts/ directory.")
    raise SystemExit(1)


def _scan_models_warning(install_path: Path, log: InstallerLogger) -> None:
    """Run a lightweight model security scan and warn about unsafe files.

    Non-blocking — only prints a warning, never halts the update.
    """
    log.step("Model Security Scan")

    models_dir = install_path / "models"
    if not models_dir.exists():
        log.sub("No models directory found. Skipping.", style="dim")
        return

    try:
        from src.utils.model_scanner import scan_models_directory

        summary = scan_models_directory(models_dir)

        if summary.total_scanned == 0:
            log.sub("No pickle-based model files found. All safe! ✅", style="success")
            return

        if summary.unsafe_count > 0:
            log.warning(
                f"{summary.unsafe_count} potentially unsafe model file(s) detected!",
                level=1,
            )
            log.sub(
                "Run 'umeairt-comfyui-installer scan-models' for details.",
                style="cyan",
            )
        else:
            log.sub(
                f"Scanned {summary.total_scanned} pickle-based model(s) — all clean. ✅",
                style="success",
            )
    except Exception:  # noqa: BLE001
        log.sub("Scanner unavailable. Install picklescan for model scanning.", style="dim")


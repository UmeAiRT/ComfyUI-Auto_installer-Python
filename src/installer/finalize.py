"""
Installation finalization — Steps 11-12.

Post-install tasks that wrap up the installation:

- **CLI** (Step 11): installs ``comfyui-installer`` into the venv so
  generated tool scripts (Update, Download-Models) work.
- **Settings** (Step 11): copies custom ComfyUI UI settings from
  the local ``scripts/comfy.settings.json``.
- **Launchers** (Step 11): generates ``.bat`` / ``.sh`` launcher and
  tool scripts.
- **Models** (Step 12): offers interactive model pack downloads
  from ``model_manifest.json``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.packaging import uv_install
from src.utils.prompts import confirm

if TYPE_CHECKING:
    from src.utils.logging import InstallerLogger


def install_cli_in_environment(
    python_exe: Path,
    log: InstallerLogger,
) -> None:
    """Install the ``comfyui-installer`` CLI into the venv.

    Uses ``pip install -e`` so the CLI stays in sync with the
    installer source. Required for generated tool scripts
    (``UmeAiRT-Update.bat``, ``UmeAiRT-Download-Models.bat``).

    Args:
        python_exe: Path to the venv Python executable.
        log: Installer logger for user-facing messages.
    """
    log.item("Installing comfyui-installer CLI into environment...")
    installer_root = Path(__file__).resolve().parent.parent.parent
    uv_install(python_exe, editable=installer_root)
    log.sub("comfyui-installer CLI available in environment.", style="success")


def install_comfy_settings(
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Copy custom ComfyUI UI settings from the local source.

    Searches for ``comfy.settings.json`` in the source ``scripts/``
    directory and copies it to ``install_path/user/default/``.

    Args:
        install_path: Root installation directory.
        log: Installer logger for user-facing messages.
    """
    import shutil

    from src.installer.environment import find_source_scripts

    source_dir = find_source_scripts()
    if source_dir is None:
        log.warning("Source scripts directory not found. Skipping settings.", level=2)
        return

    settings_src = source_dir / "comfy.settings.json"
    if not settings_src.exists():
        log.warning("comfy.settings.json not found in source scripts.", level=2)
        return

    dest = install_path / "user" / "default" / "comfy.settings.json"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and settings_src.stat().st_mtime <= dest.stat().st_mtime:
        log.sub("ComfyUI settings already up to date.", style="success")
        return

    shutil.copy2(settings_src, dest)
    log.item("ComfyUI custom settings provisioned.")


def create_launchers(
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Generate cross-platform launcher and tool scripts.

    Creates:

    - **Performance launcher**: ``--use-sage-attention --auto-launch``
      + interactive network mode prompt (local/open).
    - **LowVRAM launcher**: same + ``--lowvram --disable-smart-memory --fp8``.
    - **Tool scripts**: Model Downloader and Updater wrappers.

    The ``--listen`` address is chosen by the user at launch time
    via the prompt embedded in each launcher script (default: local
    ``127.0.0.1``, option ``0.0.0.0`` for RunPod/cloud).

    On Windows, creates ``.bat`` files; on Linux/macOS ``.sh`` files
    with the executable bit set.

    Args:
        install_path: Root installation directory.
        log: Installer logger for user-facing messages.
    """
    log.item("Creating launcher scripts...")

    is_windows = sys.platform == "win32"

    perf_args = "--use-sage-attention --auto-launch"
    lowvram_args = f"{perf_args} --disable-smart-memory --lowvram --fp8_e4m3fn-text-enc"

    launchers: list[tuple[str, str, str]] = [
        ("UmeAiRT-Start-ComfyUI", "Performance Mode", perf_args),
        ("UmeAiRT-Start-ComfyUI_LowVRAM", "Low VRAM / Stability Mode", lowvram_args),
    ]

    for name, mode_label, args in launchers:
        if is_windows:
            _write_bat_launcher(install_path, name, mode_label, args, log)
        else:
            _write_sh_launcher(install_path, name, mode_label, args, log)

    # Tool scripts (model downloader, updater)
    if is_windows:
        tools: list[tuple[str, str, str]] = [
            ("UmeAiRT-Download-Models", "Model Downloader",
             'comfyui-installer download-models --path "%InstallPath%"'),
            ("UmeAiRT-Update", "Updater",
             'comfyui-installer update --path "%InstallPath%"'),
        ]
        for tool_name, tool_label, tool_cmd in tools:
            _write_bat_tool(install_path, tool_name, tool_label, tool_cmd, log)
    else:
        tools = [
            ("UmeAiRT-Download-Models", "Model Downloader",
             'comfyui-installer download-models --path "$SCRIPT_DIR"'),
            ("UmeAiRT-Update", "Updater",
             'comfyui-installer update --path "$SCRIPT_DIR"'),
        ]
        for tool_name, tool_label, tool_cmd in tools:
            _write_sh_tool(install_path, tool_name, tool_label, tool_cmd, log)


def offer_model_downloads(
    install_path: Path,
    log: InstallerLogger,
) -> None:
    """Offer interactive model pack downloads via the unified catalog.

    Searches for ``model_manifest.json`` in multiple locations:

    1. ``install_path/scripts/``
    2. Source ``scripts/`` directory (development checkout).
    3. Parent of source ``scripts/`` directory.

    If found, prompts the user and delegates to
    :func:`src.downloader.engine.interactive_download`.

    Args:
        install_path: Root installation directory.
        log: Installer logger for user-facing messages.
    """

    # Search for catalog in multiple locations
    search_paths = [
        install_path / "scripts" / "model_manifest.json",
    ]

    # Also check source scripts directory (running from source checkout)
    from src.installer.environment import find_source_scripts
    source_dir = find_source_scripts()
    if source_dir:
        search_paths.append(source_dir / "model_manifest.json")
        search_paths.append(source_dir.parent / "model_manifest.json")

    catalog_path = None
    for path in search_paths:
        if path.exists():
            catalog_path = path
            break

    if catalog_path is None:
        log.info("No model catalog found. Searched:")
        for p in search_paths:
            log.sub(f"  {p}", style="dim")
        log.info("You can download models later with: comfyui-installer download-models")
        return

    log.sub(f"Catalog found: {catalog_path}", style="success")

    if not confirm("Would you like to download model packs now?"):
        log.sub("Model downloads skipped. You can download later with: comfyui-installer download-models")
        return

    from src.downloader.engine import interactive_download, load_catalog

    catalog = load_catalog(catalog_path)
    models_dir = install_path / "models"
    interactive_download(catalog, models_dir)


# ─── Private: Launcher script generators ─────────────────────────────────────


def _write_bat_launcher(
    install_path: Path, name: str, mode_label: str, args: str,
    log: InstallerLogger,
) -> None:
    """Write a Windows ``.bat`` ComfyUI launcher.

    Args:
        install_path: Root installation directory.
        name: Script filename without extension.
        mode_label: Human-readable label (e.g. ``"Performance Mode"``).
        args: ComfyUI CLI arguments string.
        log: Installer logger for user-facing messages.
    """
    script_path = install_path / f"{name}.bat"
    template_path = Path(__file__).parent / "templates" / "launcher.bat.template"
    if not template_path.exists():
        log.error(f"Template not found: {template_path}")
        return

    content = template_path.read_text(encoding="utf-8").format(
        name=name, mode_label=mode_label, args=args,
        install_path=str(install_path).rstrip("\\"),
    )
    script_path.write_text(content, encoding="utf-8")
    log.sub(f"{script_path.name} created.", style="success")


def _write_sh_launcher(
    install_path: Path, name: str, mode_label: str, args: str,
    log: InstallerLogger,
) -> None:
    """Write a Linux/macOS ``.sh`` ComfyUI launcher.

    Sets the executable bit after writing.

    Args:
        install_path: Root installation directory.
        name: Script filename without extension.
        mode_label: Human-readable label (e.g. ``"Performance Mode"``).
        args: ComfyUI CLI arguments string.
        log: Installer logger for user-facing messages.
    """
    script_path = install_path / f"{name}.sh"
    template_path = Path(__file__).parent / "templates" / "launcher.sh.template"
    if not template_path.exists():
        log.error(f"Template not found: {template_path}")
        return

    content = template_path.read_text(encoding="utf-8").format(
        name=name, mode_label=mode_label, args=args
    )
    script_path.write_text(content, encoding="utf-8")
    # Make executable on Unix
    import stat
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    log.sub(f"{script_path.name} created.", style="success")


def _write_bat_tool(
    install_path: Path, name: str, label: str, command: str,
    log: InstallerLogger,
) -> None:
    """Write a Windows ``.bat`` tool script (updater, downloader).

    Args:
        install_path: Root installation directory.
        name: Script filename without extension.
        label: Human-readable label for the tool.
        command: CLI command to run inside the activated environment.
        log: Installer logger for user-facing messages.
    """
    script_path = install_path / f"{name}.bat"
    template_path = Path(__file__).parent / "templates" / "tool.bat.template"
    if not template_path.exists():
        log.error(f"Template not found: {template_path}")
        return

    content = template_path.read_text(encoding="utf-8").format(
        name=name, label=label, command=command,
        install_path=str(install_path).rstrip("\\"),
    )
    script_path.write_text(content, encoding="utf-8")
    log.sub(f"{script_path.name} created.", style="success")


def _write_sh_tool(
    install_path: Path, name: str, label: str, command: str,
    log: InstallerLogger,
) -> None:
    """Write a Linux/macOS ``.sh`` tool script.

    Sets the executable bit after writing.

    Args:
        install_path: Root installation directory.
        name: Script filename without extension.
        label: Human-readable label for the tool.
        command: CLI command to run inside the activated environment.
        log: Installer logger for user-facing messages.
    """
    script_path = install_path / f"{name}.sh"
    template_path = Path(__file__).parent / "templates" / "tool.sh.template"
    if not template_path.exists():
        log.error(f"Template not found: {template_path}")
        return

    content = template_path.read_text(encoding="utf-8").format(
        name=name, label=label, command=command
    )
    script_path.write_text(content, encoding="utf-8")
    import stat
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    log.sub(f"{script_path.name} created.", style="success")

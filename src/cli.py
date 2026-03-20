"""
CLI entry point for the ComfyUI Auto-Installer.

Provides commands: install, update, download-models, info.
Uses Typer for a clean, auto-documented CLI interface.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.table import Table

from src import __version__
from src.utils.logging import console, setup_logger

app = typer.Typer(
    name="comfyui-installer",
    help="Cross-platform automated installer for ComfyUI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _clean_path(p: Path) -> Path:
    """Strip stray quotes that Windows batch files may leave in paths."""
    return Path(str(p).strip('"'))


@app.command()
def install(
    path: Path = typer.Option(
        Path.cwd(),
        "--path", "-p",
        help="Installation directory for ComfyUI.",
    ),
    install_type: str = typer.Option(
        "venv",
        "--type", "-t",
        help="Installation type: 'venv' (light) or 'conda' (full).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed output (pip, git, etc.).",
    ),
) -> None:
    """Install ComfyUI with all dependencies and custom nodes."""
    from src.installer.install import run_install

    path = _clean_path(path)
    run_install(path, install_type, verbose=verbose)


@app.command()
def update(
    path: Path = typer.Option(
        Path.cwd(),
        "--path", "-p",
        help="Root directory of existing ComfyUI installation.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed output (pip, git, etc.).",
    ),
) -> None:
    """Update ComfyUI, custom nodes, and dependencies."""
    from src.installer.updater import run_update

    path = _clean_path(path)
    run_update(path, verbose=verbose)


@app.command(name="download-models")
def download_models(
    path: Path = typer.Option(
        Path.cwd(),
        "--path", "-p",
        help="Root directory of ComfyUI installation.",
    ),
    catalog_file: Path = typer.Option(
        None,
        "--catalog", "-c",
        help="Path to model catalog JSON. Defaults to 'scripts/model_manifest.json' in install path.",
    ),
    bundle: str = typer.Option(
        "",
        "--bundle", "-b",
        help="Specific bundle to download (e.g. 'FLUX'). Empty = interactive menu.",
    ),
    variant: str = typer.Option(
        "",
        "--variant",
        help="Specific variant to download (e.g. 'fp16', 'GGUF_Q4'). Requires --bundle.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-V",
        help="Show detailed output.",
    ),
) -> None:
    """Download model packs for ComfyUI from the unified catalog."""
    from src.downloader.engine import (
        download_variant as dl_variant,
    )
    from src.downloader.engine import (
        interactive_download,
        list_bundles,
        load_catalog,
    )

    path = _clean_path(path)
    log = setup_logger(log_file=path / "logs" / "download_log.txt", verbose=verbose)
    log.banner("UmeAiRT", "ComfyUI — Model Downloader", __version__)

    # Find catalog file
    if catalog_file is None:
        catalog_file = path / "scripts" / "model_manifest.json"

    if not catalog_file.exists():
        console.print(f"[red]Catalog not found: {catalog_file}[/]")
        console.print("[dim]Place model_manifest.json in your install directory's scripts/ folder or use --catalog.[/]")
        raise typer.Exit(1)

    catalog = load_catalog(catalog_file)
    models_dir = path / "models"

    if bundle:
        # Non-interactive: download specific bundle/variant
        if bundle not in catalog.bundles:
            console.print(f"[red]Bundle '{bundle}' not found.[/]")
            list_bundles(catalog)
            raise typer.Exit(1)

        b = catalog.bundles[bundle]
        if variant:
            if variant not in b.variants:
                console.print(f"[red]Variant '{variant}' not found in {bundle}.[/]")
                console.print(f"Available: {', '.join(b.variants.keys())}")
                raise typer.Exit(1)
            log.item(f"Downloading {bundle} — {variant}...", style="cyan")
            dl_variant(b, variant, b.variants[variant], models_dir)
        else:
            # Download all variants for this bundle
            for vname, v in b.variants.items():
                log.item(f"Downloading {bundle} — {vname}...", style="cyan")
                dl_variant(b, vname, v, models_dir)
    else:
        # Interactive mode
        interactive_download(catalog, models_dir)


@app.command()
def info() -> None:
    """Display system information (GPU, Python, platform)."""
    from src.utils.commands import check_command_exists, get_command_version
    from src.utils.gpu import get_gpu_vram_info, recommend_model_quality

    console.print()
    log = setup_logger()
    log.banner("UmeAiRT", "ComfyUI — System Info", __version__)

    table = Table(title="System Information", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="bold")
    table.add_column("Value")

    # Python
    table.add_row("Python", f"{sys.version}")
    table.add_row("Platform", sys.platform)

    # GPU
    gpu = get_gpu_vram_info()
    if gpu:
        table.add_row("GPU", gpu.name)
        table.add_row("VRAM", f"{gpu.vram_gib} GB")
        table.add_row("Recommended Quality", recommend_model_quality(gpu.vram_gib))
    else:
        table.add_row("GPU", "[dim]Not detected[/]")

    # Tools
    git_ver = get_command_version("git")
    table.add_row("Git", git_ver or "[dim]Not installed[/]")

    aria2_available = check_command_exists("aria2c")
    table.add_row("aria2c", "[green]Available[/]" if aria2_available else "[dim]Not installed[/]")

    uv_ver = get_command_version("uv", "version")
    table.add_row("uv", uv_ver or "[dim]Not installed[/]")

    console.print(table)
    console.print()


@app.command()
def version() -> None:
    """Show the installer version."""
    console.print(f"comfyui-installer v{__version__}")


if __name__ == "__main__":
    app()

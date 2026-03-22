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
from src.enums import InstallType, NodeTier
from src.utils.logging import console, setup_logger
from src.utils.prompts import set_non_interactive

app = typer.Typer(
    name="umeairt-comfyui-installer",
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
    nodes: str = typer.Option(
        "full",
        "--nodes", "-n",
        help="Custom nodes bundle: 'minimal', 'umeairt', or 'full'.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Non-interactive mode: accept all defaults without prompting.",
    ),
    cuda_version: str = typer.Option(
        "",
        "--cuda",
        help="Force a specific CUDA version tag (e.g. 'cu124', 'cu130', 'cpu'). Bypasses auto-detection.",
    ),
    skip_nodes: bool = typer.Option(
        False,
        "--skip-nodes",
        help="Skip custom node installation (useful for Docker builds where nodes are handled at runtime).",
    ),
) -> None:
    """Install ComfyUI with all dependencies and custom nodes."""
    from src.installer.install import run_install

    if yes:
        set_non_interactive()

    # Validate enum values early
    try:
        install_type_enum = InstallType(install_type)
    except ValueError as e:
        raise typer.BadParameter(
            f"Invalid install type '{install_type}'. Must be one of: {', '.join(t.value for t in InstallType)}"
        ) from e
    try:
        node_tier_enum = NodeTier(nodes)
    except ValueError as e:
        raise typer.BadParameter(
            f"Invalid node tier '{nodes}'. Must be one of: {', '.join(t.value for t in NodeTier)}"
        ) from e

    path = _clean_path(path)
    run_install(
        path, install_type_enum,
        verbose=verbose, node_tier=node_tier_enum,
        cuda_version=cuda_version, skip_nodes=skip_nodes,
    )


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
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Non-interactive mode: accept all defaults without prompting.",
    ),
    nodes: str = typer.Option(
        "full",
        "--nodes", "-n",
        help="Custom nodes bundle: 'minimal', 'umeairt', or 'full'.",
    ),
) -> None:
    """Update ComfyUI, custom nodes, and dependencies."""
    from src.installer.updater import run_update

    if yes:
        set_non_interactive()

    try:
        node_tier_enum = NodeTier(nodes)
    except ValueError as e:
        raise typer.BadParameter(
            f"Invalid node tier '{nodes}'. Must be one of: {', '.join(t.value for t in NodeTier)}"
        ) from e

    path = _clean_path(path)
    run_update(path, verbose=verbose, node_tier=node_tier_enum)


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
        "--verbose", "-v",
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
            dl_variant(b, variant, b.variants[variant], models_dir, catalog)
        else:
            # Download all variants for this bundle
            for vname, v in b.variants.items():
                log.item(f"Downloading {bundle} — {vname}...", style="cyan")
                dl_variant(b, vname, v, models_dir, catalog)
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


@app.command(name="scan-models")
def scan_models(
    path: Path = typer.Option(
        ".",
        "--path", "-p",
        help="ComfyUI install path containing the 'models' directory.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show all scanned files, not just unsafe ones.",
    ),
) -> None:
    """Scan model files for malicious pickle code."""
    from src.utils.model_scanner import (
        scan_models_directory,
    )

    path = _clean_path(path)
    models_dir = path / "models"

    if not models_dir.exists():
        console.print(f"[red]Models directory not found: {models_dir}[/]")
        raise typer.Exit(1)

    console.print()
    log = setup_logger()
    log.banner("UmeAiRT", "ComfyUI — Model Security Scanner", __version__)

    console.print(f"[dim]Scanning: {models_dir}[/]\n")
    summary = scan_models_directory(models_dir)

    if summary.total_scanned == 0:
        console.print(
            "[green]✅ No pickle-based model files found. "
            "All your models use safe formats![/]"
        )
        if summary.skipped_safe_format > 0:
            console.print(
                f"[dim]   ({summary.skipped_safe_format} safetensors/"
                "gguf/onnx files skipped — inherently safe)[/]"
            )
        console.print()
        return

    # Build results table
    table = Table(
        title="Model Security Scan Results",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Status", width=6, justify="center")
    table.add_column("File", style="dim")
    table.add_column("Issues", justify="right")

    for result in summary.results:
        if not verbose and result.is_safe:
            continue

        rel_path = result.path.relative_to(models_dir)
        if result.scan_error:
            status = "[yellow]⚠️[/]"
            issues = f"[yellow]{result.error_message or 'scan error'}[/]"
        elif result.is_safe:
            status = "[green]✅[/]"
            issues = "0"
        else:
            status = "[red]❌[/]"
            issues = f"[red]{result.issues_count} suspicious[/]"

        table.add_row(status, str(rel_path), issues)

    console.print(table)
    console.print()

    # Summary line
    if summary.unsafe_count > 0:
        console.print(
            f"[red bold]⚠️  {summary.unsafe_count} potentially unsafe "
            f"file(s) detected![/]"
        )
        console.print(
            "[dim]   These files contain pickle code that could "
            "execute malicious operations.[/]"
        )
        console.print(
            "[dim]   Consider converting to .safetensors format "
            "or verifying the source.[/]"
        )
    else:
        console.print(
            f"[green]✅ All {summary.safe_count} pickle-based model(s) "
            "scanned clean.[/]"
        )

    if summary.skipped_safe_format > 0:
        console.print(
            f"[dim]   ({summary.skipped_safe_format} safetensors/"
            "gguf/onnx files skipped — inherently safe)[/]"
        )
    console.print()


@app.command()
def version() -> None:
    """Show the installer version."""
    console.print(f"umeairt-comfyui-installer v{__version__}")


if __name__ == "__main__":
    app()

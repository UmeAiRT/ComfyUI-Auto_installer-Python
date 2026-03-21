"""
Unified model download engine driven by a JSON catalog.

Replaces 8 separate PowerShell download scripts (~1200 lines) with a single
data-driven engine. The catalog format is ``model_manifest.json`` v3,
hosted in the Assets repo and consumed by both the installer and the Toolkit.

**v3 format:**

- Hierarchical structure: Family → Model → Variant
- ``_family_meta`` per family (display_name, description)
- ``_meta`` at the model level (bundle_type, loader_type, clip_type)
- ``_sources`` section with HuggingFace + ModelScope mirrors
- ``path`` — same relative path on both mirrors
- ``sha256`` per file for post-download verification
- ``bundle_type`` (``image``, ``video``, ``image_inpaint``) for Toolkit filtering
- Smart fallback: tries primary source, falls back to secondary on failure

The path_type system maps logical names (e.g. "flux_diff", "clip", "vae")
to actual directory paths relative to the models folder.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from rich.prompt import Prompt
from rich.table import Table

from src.utils.download import download_file
from src.utils.gpu import get_gpu_vram_info
from src.utils.logging import console, get_logger
from src.utils.prompts import ask_choice

if TYPE_CHECKING:
    from pathlib import Path

    from src.utils.logging import InstallerLogger

# ---------------------------------------------------------------------------
# Path type → directory mapping
# ---------------------------------------------------------------------------
# Default mapping dynamically loaded into catalog
DEFAULT_PATH_MAPPING: dict[str, str] = {
    # FLUX
    "flux_diff": "diffusion_models/FLUX",
    "flux_unet": "unet/FLUX",
    # WAN
    "wan_diff": "diffusion_models/WAN",
    "wan_unet": "unet/WAN",
    # Z-IMAGE
    "zimg_diff": "diffusion_models/Z-IMG",
    "zimg_unet": "unet/Z-IMG",
    # HiDream
    "hidream_diff": "diffusion_models/HiDream",
    "hidream_unet": "unet/HiDream",
    # LTXV
    "ltxv_diff": "diffusion_models/LTXV",
    "ltxv_ckpt": "checkpoints/LTXV",
    # LTX-2
    "ltx2_diff": "diffusion_models/LTX-2",
    # QWEN
    "qwen_diff": "diffusion_models/QWEN",
    "qwen_unet": "unet/QWEN",
    # Shared
    "clip": "clip",
    "clip_vision": "clip_vision",
    "text_encoders_t5": "text_encoders/T5",
    "text_encoders_qwen": "text_encoders/QWEN",
    "text_encoders_llama": "text_encoders/LLAMA",
    "text_encoders_gemma": "text_encoders/GEMMA-3",
    "text_encoders_ltx": "text_encoders/LTX-2",
    "latent_upscale": "latent_upscale_models",
    "melband": "diffusion_models/MelBandRoFormer",
    "vae": "vae",
    "lora": "loras",
    "lora_flux": "loras/FLUX",
    "lora_wan": "loras/WAN",
    "controlnet": "xlabs/controlnets",
    "pulid": "pulid",
    "style_models": "style_models",
    "upscale": "upscale_models",
}


# ---------------------------------------------------------------------------
# Pydantic models for the v3 catalog
# ---------------------------------------------------------------------------
class SourcesConfig(BaseModel):
    """Mirror base URLs for model downloads."""

    huggingface: str = ""
    modelscope: str = ""


class ModelFile(BaseModel):
    """A single file within a model variant.

    ``path`` is a relative path identical on both mirrors
    (e.g. ``diffusion_models/FLUX/flux1-dev-fp16.safetensors``).
    """

    path: str
    path_type: str
    sha256: str | None = None
    size_mb: int | None = None

    @property
    def filename(self) -> str:
        """Derive filename from the path."""
        return self.path.rsplit("/", 1)[-1]


class ModelVariant(BaseModel):
    """A quality variant (e.g. fp16, GGUF_Q4) with its VRAM requirement."""

    min_vram: int = 0
    files: list[ModelFile] = Field(default_factory=list)


class BundleMeta(BaseModel):
    """Metadata for a model bundle."""

    loader_type: str = ""
    clip_type: str = ""
    bundle_type: str = ""  # "image", "video", "image_inpaint"


class FamilyMeta(BaseModel):
    """Metadata for a model family."""

    display_name: str = ""
    description: str = ""


class ModelBundle(BaseModel):
    """
    A model bundle (e.g. FLUX/Dev, WAN_2.1/T2V) with metadata and variants.

    The meta field contains shared info (loader/clip type, bundle_type).
    variants maps variant names (fp16, fp8, GGUF_Q8, etc.) to ModelVariant.
    """

    meta: BundleMeta = Field(default_factory=BundleMeta)
    variants: dict[str, ModelVariant] = Field(default_factory=dict)
    family: str = ""  # parent family name


class ModelCatalog(BaseModel):
    """The complete model catalog — all bundles from the JSON file."""

    manifest_version: int = 3
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    path_mapping: dict[str, str] = Field(default_factory=lambda: DEFAULT_PATH_MAPPING.copy())
    bundles: dict[str, ModelBundle] = Field(default_factory=dict)
    families: dict[str, FamilyMeta] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Catalog loading (v3 only)
# ---------------------------------------------------------------------------
def load_catalog(path: Path) -> ModelCatalog:
    """
    Load and parse a v3 model catalog JSON file.

    v3 uses family nesting: ``FLUX → Dev → {variants}``.
    Families are flattened to compound keys: ``FLUX/Dev``.

    Args:
        path: Path to the JSON catalog file.

    Returns:
        Parsed ModelCatalog.

    Raises:
        FileNotFoundError: If catalog file doesn't exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Model catalog not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    version = raw.get("_manifest_version", 3)

    catalog = ModelCatalog(manifest_version=version)

    sources_data = raw.get("_sources", {})
    if sources_data:
        catalog.sources = SourcesConfig.model_validate(sources_data)

    path_mapping = raw.get("_path_mapping", {})
    if path_mapping:
        catalog.path_mapping.update(path_mapping)

    # Parse families — skip top-level meta keys (prefixed with "_")
    for family_name, family_data in raw.items():
        if family_name.startswith("_") or not isinstance(family_data, dict):
            continue

        # Parse family metadata (read-only — no mutation of input)
        fmeta_data = family_data.get("_family_meta", {})
        catalog.families[family_name] = FamilyMeta.model_validate(fmeta_data)

        # Each remaining key is a model within the family
        for model_name, model_data in family_data.items():
            if model_name.startswith("_") or not isinstance(model_data, dict):
                continue

            meta_data = model_data.get("_meta", {})
            meta = BundleMeta.model_validate(meta_data)

            variants: dict[str, ModelVariant] = {}
            for variant_name, variant_data in model_data.items():
                if variant_name.startswith("_"):
                    continue
                if isinstance(variant_data, dict):
                    variants[variant_name] = ModelVariant.model_validate(
                        variant_data
                    )

            compound_key = f"{family_name}/{model_name}"
            catalog.bundles[compound_key] = ModelBundle(
                meta=meta, variants=variants, family=family_name
            )

    return catalog


# ---------------------------------------------------------------------------
# URL building + source selection
# ---------------------------------------------------------------------------
def _build_download_urls(
    file_entry: ModelFile,
    sources: SourcesConfig,
) -> list[str]:
    """Build ordered list of download URLs for a file.

    Builds mirror URLs from the file's ``path`` and the catalog's
    ``_sources`` section (HuggingFace primary, ModelScope fallback).

    Args:
        file_entry: The file to download.
        sources: Mirror base URLs.

    Returns:
        Ordered list of URLs to try.
    """
    urls: list[str] = []

    primary, secondary = _pick_source_order(sources)
    if primary:
        urls.append(primary.rstrip("/") + "/" + file_entry.path)
    if secondary:
        urls.append(secondary.rstrip("/") + "/" + file_entry.path)

    return urls


def _pick_source_order(sources: SourcesConfig) -> tuple[str, str]:
    """Choose primary and secondary source based on environment.

    If ``UMEAIRT_PREFER_MODELSCOPE`` env var is set, prefer ModelScope
    (useful for users in China where HF is slow/blocked).

    Returns:
        (primary_url, secondary_url)
    """
    prefer_ms = os.environ.get("UMEAIRT_PREFER_MODELSCOPE", "").lower() in ("1", "true", "yes")

    if prefer_ms:
        return sources.modelscope, sources.huggingface
    return sources.huggingface, sources.modelscope


# ---------------------------------------------------------------------------
# Download engine
# ---------------------------------------------------------------------------
def resolve_file_path(models_dir: Path, path_type: str, filename: str, path_mapping: dict[str, str]) -> Path:
    """
    Resolve a path_type + filename to an actual file path.

    Args:
        models_dir: Root models directory.
        path_type: Logical path type (e.g. "flux_diff", "clip").
        filename: The filename.
        path_mapping: Dictionary mapping path types to subdirectories.

    Returns:
        Full path to the file.

    Raises:
        ValueError: If path_type is unknown.
    """
    subdir = path_mapping.get(path_type)
    if subdir is None:
        raise ValueError(
            f"Unknown path_type '{path_type}'. "
            f"Valid types: {', '.join(sorted(path_mapping.keys()))}"
        )
    return models_dir / subdir / filename


def download_variant(
    bundle: ModelBundle,
    variant_name: str,
    variant: ModelVariant,
    models_dir: Path,
    catalog: ModelCatalog,
) -> int:
    """
    Download all files for a specific model variant.

    Tries each mirror in order (HuggingFace first, ModelScope fallback).
    Verifies SHA256 after download when available.

    Args:
        bundle: The parent bundle.
        variant_name: Name of the variant (e.g. "fp16").
        variant: The variant with its file list.
        models_dir: Root models directory.
        catalog: The model catalog for sources and path mapping.

    Returns:
        Number of files downloaded.
    """
    log = get_logger()
    downloaded = 0
    effective_sources = catalog.sources or SourcesConfig()

    for file_entry in variant.files:
        urls = _build_download_urls(file_entry, effective_sources)

        if not urls:
            log.error(f"No download URL for {file_entry.filename}", level=2)
            continue

        dest = resolve_file_path(models_dir, file_entry.path_type, file_entry.filename, catalog.path_mapping)

        try:
            download_file(urls, dest, checksum=file_entry.sha256, quiet=False)
            downloaded += 1
        except RuntimeError as e:
            log.error(f"Failed to download {file_entry.filename}: {e}", level=2)

    return downloaded


def list_bundles(catalog: ModelCatalog) -> None:
    """Display all available model bundles in a numbered table."""
    table = Table(
        title="Available Model Bundles",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", justify="right")
    table.add_column("Family", style="bold")
    table.add_column("Model", style="bold")
    table.add_column("Type")
    table.add_column("Variants")

    for idx, (name, bundle) in enumerate(catalog.bundles.items(), 1):
        variant_names = ", ".join(bundle.variants.keys())
        bundle_type = bundle.meta.bundle_type or "—"
        if "/" in name:
            family, model = name.split("/", 1)
            fmeta = catalog.families.get(family)
            family_display = fmeta.display_name if fmeta else family
        else:
            family_display = ""
            model = name
        table.add_row(str(idx), family_display, model, bundle_type, variant_names)

    console.print(table)


def interactive_download(catalog: ModelCatalog, models_dir: Path) -> None:
    """Run an interactive download session.

    Shows a numbered table of all models. User picks by number,
    then chooses a variant for each selected model.
    """
    log = get_logger()

    # Detect GPU once, show info
    gpu = get_gpu_vram_info()
    user_vram = 0
    if gpu:
        user_vram = gpu.vram_gib
        log.item(f"GPU: {gpu.name} — {gpu.vram_gib} GB VRAM", style="success")
    else:
        log.item("No NVIDIA GPU detected.", style="info")

    # Show numbered table
    console.print()
    list_bundles(catalog)
    console.print()

    # Build indexed list
    bundle_items = list(catalog.bundles.items())

    # Single prompt: pick models by number
    console.print(
        "[bold]Enter model numbers to download "
        "(comma-separated, e.g. [cyan]1,3,5[/cyan]) "
        "or [cyan]all[/cyan], or [dim]skip[/dim]:[/bold]"
    )
    raw = Prompt.ask(">").strip().lower()

    if not raw or raw in ("skip", "s", "n", "no"):
        log.item("No models selected.", style="info")
        log.success("Model downloads complete!")
        return

    # Parse selection
    if raw == "all":
        selected_indices = list(range(len(bundle_items)))
    else:
        selected_indices = []
        for part in raw.replace(" ", "").split(","):
            try:
                idx = int(part) - 1
                if 0 <= idx < len(bundle_items):
                    selected_indices.append(idx)
                else:
                    console.print(f"[yellow]Ignoring invalid number: {part}[/yellow]")
            except ValueError:
                console.print(f"[yellow]Ignoring invalid input: {part}[/yellow]")

    if not selected_indices:
        log.item("No valid models selected.", style="info")
        log.success("Model downloads complete!")
        return

    # For each selected model, prompt variant
    for idx in selected_indices:
        compound_key, bundle = bundle_items[idx]
        if "/" in compound_key:
            family, model = compound_key.split("/", 1)
            fmeta = catalog.families.get(family)
            display = f"{fmeta.display_name if fmeta else family} — {model}"
        else:
            display = compound_key
        _prompt_variants(display, bundle, catalog, models_dir, log, user_vram)

    log.success("Model downloads complete!")


def _prompt_variants(
    display_name: str,
    bundle: ModelBundle,
    catalog: ModelCatalog,
    models_dir: Path,
    log: InstallerLogger,
    user_vram: int = 0,
) -> None:
    """Prompt user to pick variant(s) for a single bundle.

    Marks the best variant for the user's GPU with ★.
    """
    if not bundle.variants:
        return

    variant_list = list(bundle.variants.keys())
    choices = []
    valid_answers = []

    # Find the best variant that fits the user's VRAM
    recommended = ""
    if user_vram > 0:
        best_vram = 0
        for vname in variant_list:
            v = bundle.variants[vname]
            if v.min_vram and v.min_vram <= user_vram and v.min_vram > best_vram:
                best_vram = v.min_vram
                recommended = vname

    for i, vname in enumerate(variant_list):
        variant = bundle.variants[vname]
        letter = chr(65 + i)
        vram_info = f" ({variant.min_vram}GB+ VRAM)" if variant.min_vram else ""
        star = " ★" if vname == recommended else ""
        choices.append(f"{letter}) {vname}{vram_info}{star}")
        valid_answers.append(letter)

    all_letter = chr(65 + len(variant_list))
    skip_letter = chr(66 + len(variant_list))
    choices.append(f"{all_letter}) All")
    choices.append(f"{skip_letter}) Skip")
    valid_answers.extend([all_letter, skip_letter])

    answer = ask_choice(
        f"Download {display_name} models?",
        choices,
        valid_answers,
    )

    if answer == skip_letter:
        log.item(f"Skipping {display_name}.", style="info")
        return

    selected = variant_list if answer == all_letter else [variant_list[ord(answer) - 65]]

    for vname in selected:
        variant = bundle.variants[vname]
        log.item(f"Downloading {display_name} — {vname}...", style="cyan")
        count = download_variant(
            bundle, vname, variant, models_dir,
            catalog=catalog,
        )
        log.sub(f"{count} file(s) downloaded.", style="success")

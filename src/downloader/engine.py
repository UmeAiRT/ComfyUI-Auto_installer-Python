"""
Unified model download engine driven by a JSON catalog.

Replaces 8 separate PowerShell download scripts (~1200 lines) with a single
data-driven engine. The catalog format is ``model_manifest.json`` v3,
hosted in the Assets repo and consumed by both the installer and the Toolkit.

**v3 changes (vs v2):**

- Hierarchical structure: Family → Model → Variant
- ``_family_meta`` per family (display_name, description)
- ``_meta`` at the model level (bundle_type, loader_type, clip_type)

**v2 features (still supported):**

- ``_sources`` section with HuggingFace + ModelScope mirrors
- ``path`` replaces ``url`` + ``filename`` — same relative path on both mirrors
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
from rich.table import Table

from src.utils.download import download_file
from src.utils.gpu import get_gpu_vram_info
from src.utils.logging import console, get_logger
from src.utils.prompts import ask_choice

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Path type → directory mapping
# ---------------------------------------------------------------------------
PATH_TYPE_MAP: dict[str, str] = {
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
# Pydantic models for the v2 catalog
# ---------------------------------------------------------------------------
class SourcesConfig(BaseModel):
    """Mirror base URLs for model downloads."""

    huggingface: str = ""
    modelscope: str = ""


class ModelFile(BaseModel):
    """A single file within a model variant (v2 schema).

    ``path`` is a relative path identical on both mirrors
    (e.g. ``diffusion_models/FLUX/flux1-dev-fp16.safetensors``).
    The filename is derived from the path.
    """

    path: str = ""
    path_type: str
    sha256: str | None = None
    size_mb: int | None = None

    # v1 compat (deprecated, ignored if path is set)
    url: str | None = None
    filename: str | None = None
    checksum: str | None = None

    @property
    def resolved_filename(self) -> str:
        """Derive filename from path, or fall back to explicit filename."""
        if self.path:
            return self.path.rsplit("/", 1)[-1]
        return self.filename or ""

    @property
    def resolved_sha256(self) -> str | None:
        """Use sha256 if set, fall back to v1 checksum."""
        return self.sha256 or self.checksum


class ModelVariant(BaseModel):
    """A quality variant (e.g. fp16, GGUF_Q4) with its VRAM requirement."""

    min_vram: int = 0
    files: list[ModelFile] = Field(default_factory=list)


class BundleMeta(BaseModel):
    """Metadata for a model bundle."""

    base_url: str = ""  # v1 compat
    loader_type: str = ""
    clip_type: str = ""
    bundle_type: str = ""  # v2: "image", "video", "image_inpaint"


class FamilyMeta(BaseModel):
    """Metadata for a model family (v3)."""

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
    family: str = ""  # v3: parent family name


class ModelCatalog(BaseModel):
    """The complete model catalog — all bundles from the JSON file."""

    manifest_version: int = 1
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    bundles: dict[str, ModelBundle] = Field(default_factory=dict)
    families: dict[str, FamilyMeta] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------
def load_catalog(path: Path) -> ModelCatalog:
    """
    Load and parse a model catalog JSON file (v1, v2, or v3).

    v3 adds family nesting: ``FLUX → Dev → {variants}``.
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

    catalog = ModelCatalog()
    catalog.manifest_version = raw.pop("_manifest_version", 1)

    sources_data = raw.pop("_sources", {})
    if sources_data:
        catalog.sources = SourcesConfig.model_validate(sources_data)

    if catalog.manifest_version >= 3:
        _load_v3(raw, catalog)
    else:
        _load_v2(raw, catalog)

    return catalog


def _load_v2(raw: dict, catalog: ModelCatalog) -> None:
    """Parse v1/v2 flat bundle format."""
    for bundle_name, bundle_data in raw.items():
        meta_data = bundle_data.pop("_meta", {})
        meta = BundleMeta.model_validate(meta_data)

        variants: dict[str, ModelVariant] = {}
        for variant_name, variant_data in bundle_data.items():
            variants[variant_name] = ModelVariant.model_validate(variant_data)

        catalog.bundles[bundle_name] = ModelBundle(meta=meta, variants=variants)


def _load_v3(raw: dict, catalog: ModelCatalog) -> None:
    """Parse v3 hierarchical family → model → variant format."""
    for family_name, family_data in raw.items():
        if not isinstance(family_data, dict):
            continue

        # Parse family metadata
        fmeta_data = family_data.pop("_family_meta", {})
        catalog.families[family_name] = FamilyMeta.model_validate(fmeta_data)

        # Each remaining key is a model within the family
        for model_name, model_data in family_data.items():
            if not isinstance(model_data, dict):
                continue

            meta_data = model_data.pop("_meta", {})
            meta = BundleMeta.model_validate(meta_data)

            variants: dict[str, ModelVariant] = {}
            for variant_name, variant_data in model_data.items():
                if isinstance(variant_data, dict):
                    variants[variant_name] = ModelVariant.model_validate(
                        variant_data
                    )

            compound_key = f"{family_name}/{model_name}"
            catalog.bundles[compound_key] = ModelBundle(
                meta=meta, variants=variants, family=family_name
            )


# ---------------------------------------------------------------------------
# URL building + source selection
# ---------------------------------------------------------------------------
def _build_download_urls(
    file_entry: ModelFile,
    sources: SourcesConfig,
    legacy_base_url: str = "",
) -> list[str]:
    """Build ordered list of download URLs for a file.

    v2 (has ``path``): builds URLs from both mirrors.
    v1 (has ``url``): uses ``base_url + url`` or absolute URL.

    Args:
        file_entry: The file to download.
        sources: Mirror base URLs.
        legacy_base_url: v1 ``base_url`` from bundle meta.

    Returns:
        Ordered list of URLs to try.
    """
    urls: list[str] = []

    if file_entry.path:
        # v2: build from both mirrors
        primary, secondary = _pick_source_order(sources)
        if primary:
            urls.append(primary.rstrip("/") + "/" + file_entry.path)
        if secondary:
            urls.append(secondary.rstrip("/") + "/" + file_entry.path)
    elif file_entry.url:
        # v1 compat
        if file_entry.url.startswith("http"):
            urls.append(file_entry.url)
        elif legacy_base_url:
            urls.append(legacy_base_url.rstrip("/") + file_entry.url)

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
def resolve_file_path(models_dir: Path, path_type: str, filename: str) -> Path:
    """
    Resolve a path_type + filename to an actual file path.

    Args:
        models_dir: Root models directory.
        path_type: Logical path type (e.g. "flux_diff", "clip").
        filename: The filename.

    Returns:
        Full path to the file.

    Raises:
        ValueError: If path_type is unknown.
    """
    subdir = PATH_TYPE_MAP.get(path_type)
    if subdir is None:
        raise ValueError(
            f"Unknown path_type '{path_type}'. "
            f"Valid types: {', '.join(sorted(PATH_TYPE_MAP.keys()))}"
        )
    return models_dir / subdir / filename


def download_variant(
    bundle: ModelBundle,
    variant_name: str,
    variant: ModelVariant,
    models_dir: Path,
    sources: SourcesConfig | None = None,
) -> int:
    """
    Download all files for a specific model variant.

    Tries each mirror in order (HuggingFace first, ModelScope fallback).
    Verifies SHA256 after download when available.

    Args:
        bundle: The parent bundle (for legacy base_url).
        variant_name: Name of the variant (e.g. "fp16").
        variant: The variant with its file list.
        models_dir: Root models directory.
        sources: Mirror URLs (v2). Falls back to bundle base_url (v1).

    Returns:
        Number of files downloaded.
    """
    log = get_logger()
    downloaded = 0
    effective_sources = sources or SourcesConfig()

    for file_entry in variant.files:
        filename = file_entry.resolved_filename
        sha256 = file_entry.resolved_sha256

        urls = _build_download_urls(
            file_entry,
            effective_sources,
            legacy_base_url=bundle.meta.base_url,
        )

        if not urls:
            log.error(f"No download URL for {filename}", level=2)
            continue

        dest = resolve_file_path(models_dir, file_entry.path_type, filename)

        try:
            download_file(urls, dest, checksum=sha256, quiet=False)
            downloaded += 1
        except RuntimeError as e:
            log.error(f"Failed to download {filename}: {e}", level=2)

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
    raw = input("> ").strip().lower()

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
    log: object,
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
            sources=catalog.sources,
        )
        log.sub(f"{count} file(s) downloaded.", style="success")

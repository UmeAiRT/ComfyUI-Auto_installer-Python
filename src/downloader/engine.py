"""
Unified model download engine driven by a JSON catalog.

Replaces 8 separate PowerShell download scripts (~1200 lines) with a single
data-driven engine. The catalog format is based on the umeairt_bundles.json
pattern from ComfyUI-UmeAiRT-Toolkit.

The path_type system maps logical names (e.g. "flux_diff", "clip", "vae")
to actual directory paths relative to the models folder.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field
from rich.table import Table

from src.utils.download import download_file
from src.utils.gpu import display_gpu_recommendations
from src.utils.logging import console, get_logger
from src.utils.prompts import ask_choice

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
    "hidream_diff": "diffusion_models/HIDREAM",
    "hidream_unet": "unet/HIDREAM",
    # LTX
    "ltx_diff": "diffusion_models/LTX",
    "ltx_unet": "unet/LTX",
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
    "clip_vision": "clip_vision",
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
# Pydantic models for the catalog
# ---------------------------------------------------------------------------
class ModelFile(BaseModel):
    """A single file within a model variant."""

    url: str
    path_type: str
    filename: str
    checksum: str | None = None


class ModelVariant(BaseModel):
    """A quality variant (e.g. fp16, GGUF_Q4) with its VRAM requirement."""

    min_vram: int = 0
    files: list[ModelFile] = Field(default_factory=list)


class BundleMeta(BaseModel):
    """Metadata for a model bundle."""

    base_url: str = ""
    loader_type: str = ""
    clip_type: str = ""


class ModelBundle(BaseModel):
    """
    A model bundle (e.g. FLUX, WAN2.1) with metadata and quality variants.

    The _meta field contains shared info (base_url, loader/clip type).
    All other keys are quality variant names (fp16, fp8, GGUF_Q8, etc.).
    """

    meta: BundleMeta = Field(default_factory=BundleMeta)
    variants: dict[str, ModelVariant] = Field(default_factory=dict)


class ModelCatalog(BaseModel):
    """The complete model catalog — all bundles from the JSON file."""

    bundles: dict[str, ModelBundle] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------
def load_catalog(path: Path) -> ModelCatalog:
    """
    Load and parse a model catalog JSON file (umeairt_bundles.json format).

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

    for bundle_name, bundle_data in raw.items():
        meta_data = bundle_data.pop("_meta", {})
        meta = BundleMeta.model_validate(meta_data)

        variants: dict[str, ModelVariant] = {}
        for variant_name, variant_data in bundle_data.items():
            variants[variant_name] = ModelVariant.model_validate(variant_data)

        catalog.bundles[bundle_name] = ModelBundle(meta=meta, variants=variants)

    return catalog


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
) -> int:
    """
    Download all files for a specific model variant.

    Args:
        bundle: The parent bundle (for base_url).
        variant_name: Name of the variant (e.g. "fp16").
        variant: The variant with its file list.
        models_dir: Root models directory.

    Returns:
        Number of files downloaded.
    """
    log = get_logger()
    downloaded = 0

    for file_entry in variant.files:
        # Build full URL: base_url + relative url
        if file_entry.url.startswith("http"):
            url = file_entry.url
        else:
            url = bundle.meta.base_url.rstrip("/") + file_entry.url

        dest = resolve_file_path(models_dir, file_entry.path_type, file_entry.filename)

        try:
            download_file(url, dest, checksum=file_entry.checksum)
            downloaded += 1
        except RuntimeError as e:
            log.error(f"Failed to download {file_entry.filename}: {e}", level=2)

    return downloaded


def list_bundles(catalog: ModelCatalog) -> None:
    """Display all available model bundles in a table."""
    table = Table(title="Available Model Bundles", show_header=True, header_style="bold cyan")
    table.add_column("Bundle", style="bold")
    table.add_column("Variants")
    table.add_column("Type")

    for name, bundle in catalog.bundles.items():
        variant_names = ", ".join(bundle.variants.keys())
        loader = bundle.meta.loader_type or "—"
        table.add_row(name, variant_names, loader)

    console.print(table)


def interactive_download(catalog: ModelCatalog, models_dir: Path) -> None:
    """
    Run an interactive download session.

    Shows GPU info, lists bundles, lets the user pick what to download.
    Replaces ALL 8 PowerShell Download-*.ps1 scripts.
    """
    log = get_logger()

    # Show GPU recommendations
    gpu = display_gpu_recommendations()

    # Show available bundles
    console.print()
    list_bundles(catalog)
    console.print()

    # For each bundle, ask the user
    for bundle_name, bundle in catalog.bundles.items():
        if not bundle.variants:
            continue

        # Build choices from variants
        variant_list = list(bundle.variants.keys())
        choices = []
        valid_answers = []

        for i, vname in enumerate(variant_list):
            variant = bundle.variants[vname]
            letter = chr(65 + i)  # A, B, C, ...
            vram_info = f" ({variant.min_vram}GB+ VRAM)" if variant.min_vram else ""
            choices.append(f"{letter}) {vname}{vram_info}")
            valid_answers.append(letter)

        # Add "All" and "Skip" options
        all_letter = chr(65 + len(variant_list))
        skip_letter = chr(66 + len(variant_list))
        choices.append(f"{all_letter}) All")
        choices.append(f"{skip_letter}) Skip")
        valid_answers.extend([all_letter, skip_letter])

        answer = ask_choice(
            f"Download {bundle_name} models?",
            choices,
            valid_answers,
        )

        if answer == skip_letter:
            log.item(f"Skipping {bundle_name}.", style="info")
            continue

        # Determine which variants to download
        if answer == all_letter:
            selected_variants = variant_list
        else:
            idx = ord(answer) - 65
            selected_variants = [variant_list[idx]]

        # Download selected variants
        for vname in selected_variants:
            variant = bundle.variants[vname]
            log.item(f"Downloading {bundle_name} — {vname}...", style="cyan")
            count = download_variant(bundle, vname, variant, models_dir)
            log.sub(f"{count} file(s) downloaded.", style="success")

    log.success("Model downloads complete!")

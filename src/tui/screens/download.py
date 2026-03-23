"""
Download Screen — Browse model catalog and download bundles.

Two-step flow:
1. Select a model bundle (FLUX/Dev, WAN/T2V, etc.)
2. Select a variant (fp16, GGUF_Q4, etc.) with VRAM recommendation
Then download via the existing engine.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.containers import Center, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, LoadingIndicator, Static

if TYPE_CHECKING:
    from pathlib import Path

    from textual.app import ComposeResult


def _detect_vram() -> float | None:
    """Detect GPU VRAM in GiB."""
    try:
        from src.utils.gpu import get_gpu_vram_info
        gpu = get_gpu_vram_info()
        if gpu:
            return gpu.vram_gib
    except Exception:
        pass
    return None


def _find_catalog(install_path: Path) -> Path | None:
    """Find the model manifest file."""
    catalog_path = install_path / "scripts" / "model_manifest.json"
    if catalog_path.exists():
        return catalog_path
    return None


def _sanitize_id(key: str) -> str:
    """Sanitize a string for use as a Textual CSS identifier."""
    import re
    return re.sub(r"[^a-zA-Z0-9_-]", "-", key)


class DownloadScreen(Screen):
    """Model catalog browser — select bundle then variant."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("up", "move_up", show=False, priority=True),
        Binding("down", "move_down", show=False, priority=True),
        Binding("enter", "press_focused", show=False, priority=True),
    ]

    def __init__(self, install_path: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.install_path = install_path
        self.vram_gib = _detect_vram()
        self.catalog = None
        self.selected_bundle_key: str | None = None
        self._button_ids: list[str] = []
        self._id_to_key: dict[str, str] = {}  # sanitized id -> bundle key

    def compose(self) -> ComposeResult:
        """Show loading state initially."""
        yield Header(show_clock=True)
        with VerticalScroll(id="download-container"):
            yield LoadingIndicator(id="dl-loading")
            yield Vertical(id="dl-content")
        yield Footer()

    def on_mount(self) -> None:
        """Load catalog and show bundle list."""
        self.run_worker(self._load_catalog, thread=True)

    async def _load_catalog(self) -> None:
        """Load catalog in a worker thread."""
        catalog_path = _find_catalog(self.install_path)
        if catalog_path:
            from src.downloader.engine import load_catalog
            self.catalog = load_catalog(catalog_path)
        self.app.call_from_thread(self._show_bundle_list)

    def _show_bundle_list(self) -> None:
        """Display the list of available model bundles."""
        loading = self.query_one("#dl-loading", LoadingIndicator)
        loading.display = False
        content = self.query_one("#dl-content", Vertical)
        content.remove_children()

        if not self.catalog or not self.catalog.bundles:
            content.mount(Center(Static(
                "[yellow]⚠ No model catalog found.[/]\n\n"
                "[dim]Place model_manifest.json in scripts/ folder.[/dim]"
            )))
            content.mount(Center(Button("← Back", id="btn-back", classes="menu-button")))
            self._button_ids = ["btn-back"]
            return

        vram_str = f"{self.vram_gib:.0f} GB" if self.vram_gib else "unknown"
        content.mount(Center(Static(
            f"⬇️ [b]Model Downloader[/b]\n\n"
            f"[b]GPU VRAM:[/b] {vram_str}  •  "
            f"[dim]Select a model to download[/dim]",
            classes="dl-title",
        )))

        self._button_ids = []

        # Group bundles by family
        families: dict[str, list[str]] = {}
        for bundle_key, bundle in self.catalog.bundles.items():
            family = bundle.family or bundle_key.split("/")[0]
            families.setdefault(family, []).append(bundle_key)

        for family_name, bundle_keys in families.items():
            # Family header
            family_meta = self.catalog.families.get(family_name)
            display = family_meta.display_name if family_meta and family_meta.display_name else family_name
            desc = f"  [dim]{family_meta.description}[/dim]" if family_meta and family_meta.description else ""
            content.mount(Center(Static(f"\n[b]{display}[/b]{desc}", classes="dl-family-header")))

            for bkey in bundle_keys:
                bundle = self.catalog.bundles[bkey]
                model_name = bkey.split("/", 1)[-1] if "/" in bkey else bkey
                variant_count = len(bundle.variants)
                btn_type = f" [dim]({bundle.meta.bundle_type})[/dim]" if bundle.meta.bundle_type else ""
                btn_id = f"btn-bundle-{_sanitize_id(bkey)}"
                self._id_to_key[btn_id] = bkey
                self._button_ids.append(btn_id)

                content.mount(Center(Button(
                    f"  {model_name}{btn_type}  —  {variant_count} variant{'s' if variant_count > 1 else ''}",
                    id=btn_id,
                    classes="menu-button",
                )))

        self._button_ids.append("btn-back")
        content.mount(Static(""))
        content.mount(Center(Button("← Back", id="btn-back", classes="menu-button")))

        # Focus first bundle button
        if self._button_ids:
            with contextlib.suppress(Exception):
                self.query_one(f"#{self._button_ids[0]}", Button).focus()

    def _show_variant_list(self, bundle_key: str) -> None:
        """Show variants for a specific bundle."""
        self.selected_bundle_key = bundle_key
        content = self.query_one("#dl-content", Vertical)
        content.remove_children()

        bundle = self.catalog.bundles[bundle_key]
        model_name = bundle_key.split("/", 1)[-1] if "/" in bundle_key else bundle_key
        family = bundle_key.split("/")[0] if "/" in bundle_key else ""

        content.mount(Center(Static(
            f"⬇️ [b]{family} — {model_name}[/b]\n\n"
            f"[dim]Choose a quality variant to download[/dim]",
            classes="dl-title",
        )))

        self._button_ids = []

        for vname, variant in bundle.variants.items():
            total_mb = sum(f.size_mb or 0 for f in variant.files)
            size_str = f"{total_mb / 1024:.1f} GB" if total_mb > 1024 else f"{total_mb} MB"
            file_count = len(variant.files)
            min_vram = variant.min_vram

            # VRAM recommendation
            if self.vram_gib and min_vram:
                if self.vram_gib >= min_vram:
                    vram_tag = f" [green]✓ fits {min_vram}GB+[/green]"
                else:
                    vram_tag = f" [red]⚠ needs {min_vram}GB[/red]"
            elif min_vram:
                vram_tag = f" [dim]({min_vram}GB VRAM)[/dim]"
            else:
                vram_tag = ""

            btn_id = f"btn-var-{_sanitize_id(vname)}"
            self._id_to_key[btn_id] = vname
            self._button_ids.append(btn_id)

            content.mount(Center(Button(
                f"  {vname}  —  {file_count} file{'s' if file_count > 1 else ''}, "
                f"~{size_str}{vram_tag}",
                id=btn_id,
                classes="menu-button",
            )))

        # Back button
        self._button_ids.append("btn-var-back")
        content.mount(Static(""))
        content.mount(Center(Button("← Back to bundles", id="btn-var-back", classes="menu-button")))

        if self._button_ids:
            with contextlib.suppress(Exception):
                self.query_one(f"#{self._button_ids[0]}", Button).focus()

    def _start_download(self, btn_id: str) -> None:
        """Exit TUI and run download command."""
        variant_name = self._id_to_key.get(btn_id, "")
        self.app.exit(result=f'download-models --bundle "{self.selected_bundle_key}" --variant "{variant_name}"')

    # ── Navigation ──
    def _get_focused_index(self) -> int:
        focused = self.focused
        if isinstance(focused, Button) and focused.id in self._button_ids:
            return self._button_ids.index(focused.id)
        return -1

    def action_move_down(self) -> None:
        idx = self._get_focused_index()
        if idx >= 0 and idx < len(self._button_ids) - 1:
            with contextlib.suppress(Exception):
                self.query_one(f"#{self._button_ids[idx + 1]}", Button).focus()

    def action_move_up(self) -> None:
        idx = self._get_focused_index()
        if idx > 0:
            with contextlib.suppress(Exception):
                self.query_one(f"#{self._button_ids[idx - 1]}", Button).focus()

    def action_press_focused(self) -> None:
        focused = self.focused
        if isinstance(focused, Button):
            focused.press()

    def action_go_back(self) -> None:
        if self.selected_bundle_key:
            self.selected_bundle_key = None
            self._show_bundle_list()
        else:
            self.app.pop_screen()

    # ── Button handlers ──
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""

        if bid == "btn-back":
            self.app.pop_screen()

        elif bid == "btn-var-back":
            self.selected_bundle_key = None
            self._show_bundle_list()

        elif bid.startswith("btn-bundle-"):
            bundle_key = self._id_to_key.get(bid, "")
            self._show_variant_list(bundle_key)

        elif bid.startswith("btn-var-"):
            self._start_download(bid)

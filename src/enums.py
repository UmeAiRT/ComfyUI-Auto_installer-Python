"""
Shared enums and exceptions for the installer.

Centralises magic strings (``"venv"``/``"conda"``, ``"minimal"``/``"umeairt"``/
``"full"``) into type-safe :class:`~enum.StrEnum` members.  ``StrEnum`` allows
transparent comparison with plain strings, so JSON configs and CLI args keep
working without conversion boilerplate.

Also defines :class:`InstallerFatalError` — a structured replacement for the
bare ``raise SystemExit(1)`` calls scattered across the codebase.
"""

from __future__ import annotations

from enum import StrEnum


class InstallType(StrEnum):
    """Supported Python environment types."""

    VENV = "venv"
    CONDA = "conda"


class NodeTier(StrEnum):
    """Custom-node bundle tiers (additive hierarchy)."""

    MINIMAL = "minimal"
    UMEAIRT = "umeairt"
    FULL = "full"


class InstallerFatalError(Exception):
    """Fatal error that should abort the installation.

    Raised by installer sub-modules instead of ``raise SystemExit(1)`` so
    that the orchestrator (:func:`~src.installer.install.run_install`) can
    catch it cleanly, log the error, and exit with a non-zero code.
    """

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0-alpha.1] — Python Rewrite

### Added

- **Full Python CLI** (`comfyui-installer`) replacing all PowerShell scripts — commands: `install`, `update`, `download-models`, `info`, `version`.
- **Cross-platform support** — Windows (.bat), Linux/macOS (.sh) launchers and installer scripts.
- **Pydantic configuration** — typed, validated config models for `dependencies.json` and user settings.
- **Verbose mode** (`-v` / `--verbose`) — hides pip/git subprocess output by default, shows with flag.
- **Step counter** — `[Step X/12]` progress indicator across both installation phases.
- **Additive-only node manifest** (`custom_nodes.json`) — replaces destructive snapshot system. User-installed nodes are never removed.
- **Git clone retry** — 3 attempts with 300s timeout, shallow clone (`--depth 1`) on retries 2+.
- **Internalized Triton/SageAttention** — version-constrained installation based on PyTorch compatibility matrix (inspired by DazzleML).
- **Unified model downloader** — catalog-driven system replacing 8 separate PowerShell scripts.
- **Launcher generation** — 4 scripts generated at install time: Start (Performance), Start (LowVRAM), Download Models, Update.
- **Bootstrap version detection** — `Install.bat`/`Install.sh` compare installed vs repo version and prompt before updating.
- **GPU info command** — `comfyui-installer info` displays GPU, VRAM, Python, and tool versions.
- **Agentic documentation** — `AGENTS.md`, `.cursorrules`, `docs/codemaps/` with mermaid diagrams.
- **203 automated tests** — unit and integration tests with pytest, 56% coverage.
- **CI/CD pipeline** — GitHub Actions with Python 3.11-3.13 × Ubuntu/Windows matrix, Ruff linting, Bandit security audit, pip-audit CVE scan, and coverage threshold.

### Changed

- **Architecture**: Migrated from PowerShell (`.ps1`) to Python (`src/`), reducing ~3700 lines of scripts.
- **Installer Isolation**: The bootstrap script (`install.bat`) now creates a dedicated, isolated `.installer_venv` to prevent polluting the global Python environment.
- **Path Mapping Engine**: The internal `PATH_TYPE_MAP` is now decoupled, allowing paths to be dynamically defined via `model_manifest.json`.
- **Node management**: `custom_nodes.json` (JSON manifest) replaces `custom_nodes.csv` + `snapshot.json`.
- **Dependency management**: `uv` as primary package manager with `pip` fallback.
- **Logging**: `InstallerLogger` with 4 levels (step/item/sub/info) replacing `Write-Log` PowerShell module.

### Removed

- All PowerShell scripts (`.ps1`, `.psm1`) — replaced by Python.
- `snapshot.json` — replaced by additive manifest.
- `custom_nodes.csv` — replaced by `custom_nodes.json`.
- `whl/` directory (28 MB of bundled wheels) — now downloaded via URL.
- External script download for Triton/SageAttention — security risk eliminated.
- Old root `.bat` launchers — now auto-generated at install time.

### Security

- **Eliminated external script execution** — no more downloading `.py` files from the internet and running them.
- **Secure subprocess calls** — all commands use explicit argument lists (no `shell=True`).
- **HTTPS only** — all download URLs validated.

### Fixed

- Double arrow prefix on uv/pip install log lines.
- Step counter overflow (was showing 10/9).
- Verbose flag not working with lowercase `-v`.
- Duplicate log lines for uv/pip commands.
- Git clone timeouts on larger repositories.

## [4.x and earlier] — PowerShell Era

See git history for the original PowerShell-based installer.
Notable milestones:

- CUDA 13.0 support
- Miniconda integration
- Triton/SageAttention compilation
- Multi-model download scripts (FLUX, WAN, HiDream, LTX, QWEN)
- `repo-config.json` for fork customization
- Junction-based architecture for clean updates
- CVE-2025-69277 fix (path traversal)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0-alpha.2] — Hardening & Optimization Engine

### Added

- **Config-driven optimizations** — `optimizations.packages[]` in `dependencies.json` replaces hardcoded Triton/SageAttention logic. Supports per-platform packages, GPU/OS filters (`requires`), torch version constraints, and retry options. Adding a new optimization = 1 JSON block, zero Python code.
- **FlashAttention** — added as a Linux+NVIDIA-only package via the new optimization engine.
- **`skip_step()` logger** — `InstallerLogger.skip_step()` decrements `total_steps` and logs a dimmed message when a step is conditionally skipped, keeping the progress counter accurate.
- **80 new tests** — 6 new test files covering `commands`, `prompts`, `nodes`, `updater`, `gpu`, and `download` modules.

### Changed

- **Docker: CUDA 13.0 runtime** — base image changed from `python:3.12-slim` (CPU-only) to `nvidia/cuda:13.0.2-runtime-ubuntu22.04` for full RTX 50X0/40X0/30X0 GPU support.
- **Docker: standalone uv** — replaced `pip install uv` with the standalone binary via `curl` (matches bootstrap approach).
- **Docker: fast startup** — replaced `user: root` + `chown -R` at every boot with `user: "1000:1000"` (fixed UID created at build time).
- **Error handling** — `SystemExit(1)` in updater replaced with `InstallerFatalError` for consistent error handling.
- **Explicit `cuda_tag`** — removed hardcoded `"cu130"` defaults from `install_core_dependencies`, `install_python_packages`, `install_wheels` function signatures.
- **macOS PyTorch** — improved package detection to derive names dynamically instead of relying on fragile string matching.
- **Install.sh** — aligned with `Install.bat` by adding `--python-preference only-system` as first venv creation attempt.
- **CI coverage threshold** — bumped from 55% to 70%.

### Fixed

- Updater step counter becoming inaccurate when `custom_nodes.json` is missing (now uses `skip_step()`).
- Logger singleton state leaking between tests (added `autouse` reset fixture in `conftest.py`).
- Redundant import of `CommandError` in `nodes.py`.
- Extra blank lines between functions in `environment.py`.

## [5.0.0-alpha.1] — Python Rewrite

### Added

- **Universal Hardware Support** — Auto-detects and configs PyTorch for NVIDIA (CUDA 13.0/12.8), AMD (ROCm 7.1/DirectML), and Apple Silicon (MPS).
- **Full Python CLI** (`umeairt-comfyui-installer`) replacing all PowerShell scripts — commands: `install`, `update`, `download-models`, `info`, `version`.
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
- **GPU info command** — `umeairt-comfyui-installer info` displays GPU, VRAM, Python, and tool versions.
- **Agentic documentation** — `AGENTS.md`, `.cursorrules`, `docs/codemaps/` with mermaid diagrams.
- **374 automated tests** — unit and integration tests with pytest, 70% coverage.
- **CI/CD pipeline** — Fast PR linting/testing matrix (`ci.yml`), plus a rigorous E2E manual workflow (`integration.yml`) that spins up a Windows VM, does a full install, and stream-validates all PyTorch/tool SHA-256 hashes.
- **Docker support** — `Dockerfile` + `docker-compose.yml` with CUDA 13.0 runtime and `--skip-nodes` for lightweight images. Custom nodes installed at runtime via entrypoint into persistent volumes. Docker CI smoke test in GitHub Actions.
- **Model security scanner** — `scan-models` CLI command using `picklescan` to detect malicious pickle code in `.ckpt`/`.pt`/`.pth` model files. Non-blocking warning integrated into the update flow.

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

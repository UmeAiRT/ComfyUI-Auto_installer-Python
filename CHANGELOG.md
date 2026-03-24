# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.1.2] — SageAttention Per-Architecture Builds & Bootstrap Fallback

### Added

- **Per-architecture SageAttention wheels** — SM80, SM86, SM89, SM90 (Linux), SM100 (RTX 5090) each get a dedicated wheel with natively compiled CUDA kernels. Resolves "SM89 kernel not available" errors on RTX 40XX GPUs.
- **SM100 (Blackwell) support** — SA2 builds for RTX 5090 on both Linux and Windows.
- **Bootstrap triple-source fallback** — `get.umeai.art` scripts now try GitHub (git), then HuggingFace (ZIP), then ModelScope (ZIP). Git is no longer a hard prerequisite on Windows.
- **Release ZIP mirroring** — `release.yml` now uploads a `latest.zip` source archive to HuggingFace and ModelScope for fallback downloads.
- **Bootstrap integrity check** — verifies `Install.bat` and `pyproject.toml` presence after download.

### Fixed

- **SageAttention checksum verification** — two-pass lookup (full path first, basename fallback) prevents stale checksums from the old flat manifest entry.
- **InsightFace wheel restored** — pre-compiled Windows wheel reinstated in `dependencies.json` (was incorrectly moved to standard packages).
- **UV detection** — `find_uv()` now checks the local `scripts/uv/` directory before the system PATH, correctly detecting the bootstrap-installed binary.
- **ModelScope uploads** — removed invalid `endpoint=` parameter from `upload_file()` calls; endpoint is set on `HubApi()` constructor.
- **SM90 Windows builds removed** — Hopper GPUs (H100/H200) are datacenter-only Linux hardware.

### Changed

- **416 tests** — all passing.

## [5.1.0] — TUI Manager & Launcher Consolidation

### Added

- **TUI Manager** — Full terminal UI (`umeairt-comfyui-installer` with no subcommand) built with Textual, featuring:
  - **Home screen** — Detect installed ComfyUI, show Launch / Update / Download / Reinstall / Info options.
  - **Launch screen** — VRAM mode selector (Performance / Normal / Low) with GPU VRAM auto-detection, listen address, SageAttention toggle, auto-browser toggle — all on a single row.
  - **Download screen** — Interactive model bundle browser with variant selection and progress tracking.
  - **Install screen** — Path input and environment type selection for fresh installs.
  - **Info screen** — System info display (GPU, Python, installed packages).
- **`UserSettings` model** (`src/settings.py`) — Persistent JSON-based user preferences for listen address, VRAM mode, SageAttention, auto-browser, and extra args.
- **`--reinstall` flag** — Clean reinstall option that preserves models and output data.
- **`UmeAiRT-Manager` script** — Single launcher replacing `UmeAiRT-Update` + `UmeAiRT-Download-Models` scripts. Opens the TUI manager.
- **23 new tests** for `UserSettings` — defaults, save/load round-trip, corrupt file handling, all VRAM modes, DirectML detection, extra args.

### Changed

- **Launcher consolidation** — 4 generated scripts → 3: Performance, LowVRAM, Manager (one entry point for update, download, reinstall, settings).
- **Settings merged into Launcher** — Listen address, SageAttention, and auto-browser settings moved from a separate Settings screen into the Launch screen.
- **Portable bundle** — `UmeAiRT-Download-Models.bat` replaced by `UmeAiRT-Manager.bat` (launches TUI).
- **Coverage** — `src/tui/*` excluded from CI coverage (interactive terminal widgets). Total coverage maintained at 70%+.
- **416 tests** — up from 393 (all passing).

### Fixed

- **20 ruff lint errors** in TUI files (TC003, F401, SIM105, SIM117, E501).
- **3 bandit warnings** — `# nosec B104` for user-chosen `0.0.0.0` bind address, `# nosec B605` for static `os.system("cls")`.
- **Stale imports** — Removed `SettingsScreen` import and F2 binding from `app.py`.
- **Test failures** — Updated tool script count (2→1), network prompt test, snapshot tests.

## [5.0.0] — Stable Release

### Changed

- **Version bump** — `5.0.0a3` → `5.0.0` (Production/Stable).
- **Docstrings** — `run_install()` and `CONTRIBUTING.md` now reference "13 steps" (was "12").
- **CONTRIBUTING.md** — Fixed repository clone URL to `ComfyUI-Auto_installer-Python`.

### Removed

- **`bootstrap/` legacy folder** — 4 unused scripts (`install.bat`, `install.sh`, `remote-install.ps1`, `remote-install.sh`) from the PowerShell era. The real entry points are `Install.bat` and `Install.sh` at the project root.

## [5.0.0-alpha.3] — SageAttention CI & Docker Lite

### Added

- **SageAttention CI workflow** — `build-sageattention.yml` compiles SA2 (v2.2.0, sm_80+PTX for Python 3.11/3.12/3.13) and SA3 (v1.0.0, sm_100 Blackwell) wheels. Automated manifest update job uploads wheels + SHA256 checksums to HuggingFace Assets.
- **Docker lite variant** — `docker build --build-arg VARIANT=lite` produces a ~2 GB image without pre-installed PyTorch. The entrypoint detects missing venv and runs a full install on first boot (~5-10 min), then caches in the persistent volume. Also available as `lite-cloud` with JupyterLab.
- **Docker image variants** — 4 published images: `latest`, `latest-cloud`, `latest-lite`, `latest-lite-cloud`.
- **JupyterLab bash default** — Jupyter terminals default to bash via `--ServerApp.terminado_settings`.
- **JupyterLab trash disabled** — `--FileContentsManager.delete_to_trash=False` saves disk space in containers.
- **Entrypoint first-run detection** — checks for `/app/scripts/venv` existence to decide whether to run initial install.

### Changed

- **Docker base image** — switched from `nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04` to `nvidia/cuda:13.0.2-runtime-ubuntu24.04` (cuDNN removed — PyTorch bundles its own).
- **Docker build optimization** — lite variants skip `build-essential` and `python3.12-dev` entirely, standard variants include them for compilation.
- **CI SageAttention images** — switched from `cudnn-devel` to `devel` (cuDNN unnecessary for CUDA kernel compilation).
- **SageAttention build strategy** — SA2 uses `8.0+PTX` (single native arch + PTX forward compat) to prevent OOM errors during CI compilation.
- **`.dockerignore` expanded** — excludes `.github/`, `docs/`, `bootstrap/`, IDE configs, and `docker-compose.yml`.
- **`dependencies.json`** — updated SageAttention wheel entries with correct HuggingFace URLs, versions (SA2 2.2.0, SA3 1.0.0), and SHA256 checksums.
- **406 tests** — up from 369 (all passing).

### Fixed

- **SageAttention CI OOM** — compilation now uses `MAX_JOBS=1` and single-arch `8.0+PTX` strategy.
- **HuggingFace repo name** — corrected `HF_REPO` to `UmeAiRT/ComfyUI-Auto-Installer-Assets`.
- **SA3 wheel build** — fixed `setup.py bdist_wheel` for subdirectory package structure.

## [5.0.0-alpha.2] — Hardening & Optimization Engine

### Added

- **Config-driven optimizations** — `optimizations.packages[]` in `dependencies.json` replaces hardcoded Triton/SageAttention logic. Supports per-platform packages, GPU/OS filters (`requires`), torch version constraints, and retry options. Adding a new optimization = 1 JSON block, zero Python code.
- **FlashAttention** — added as a Linux+NVIDIA-only package via the new optimization engine.
- **`skip_step()` logger** — `InstallerLogger.skip_step()` decrements `total_steps` and logs a dimmed message when a step is conditionally skipped, keeping the progress counter accurate.
- **Docker cloud variant** — `docker build --build-arg VARIANT=cloud` adds JupyterLab alongside ComfyUI for RunPod/cloud deployments. Runtime env vars: `JUPYTER_ENABLE`, `JUPYTER_TOKEN`, `JUPYTER_PORT`.
- **Docker `NODE_TIER`** — environment variable to control which custom node bundle installs at container startup (`minimal`, `umeairt`, `full`). Also added `--nodes` flag to the `update` CLI command.
- **GHCR auto-publish** — `docker-publish.yml` workflow builds and pushes both `standard` and `cloud` Docker images to `ghcr.io/umeairt/comfyui` on version tags.
- **80 new tests** — 6 new test files covering `commands`, `prompts`, `nodes`, `updater`, `gpu`, and `download` modules.

### Changed

- **Docker: CUDA 13.0 runtime** — base image changed from `python:3.12-slim` (CPU-only) to `nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04` for full RTX 50X0/40X0/30X0 GPU support.
- **Docker: standalone uv** — replaced `pip install uv` with the standalone binary via `curl` (matches bootstrap approach).
- **Docker: fast startup** — replaced `user: root` + `chown -R` at every boot with `user: "1000:1000"` (fixed UID created at build time).
- **Error handling** — `SystemExit(1)` in updater replaced with `InstallerFatalError` for consistent error handling.
- **Explicit `cuda_tag`** — removed hardcoded `"cu130"` defaults from `install_core_dependencies`, `install_python_packages`, `install_wheels` function signatures.
- **macOS PyTorch** — improved package detection to derive names dynamically instead of relying on fragile string matching.
- **Install.sh** — aligned with `Install.bat` by adding `--python-preference only-system` as first venv creation attempt.
- **CI coverage threshold** — bumped from 55% to 70%.

### Fixed

- **Docker: CRLF line endings** — `entrypoint.sh` broken on Linux due to Windows `\r\n` endings. Fixed by adding `sed -i 's/\r$//'` in Dockerfile and `.gitattributes` enforcing LF on `.sh` files.
- **Docker: PEP 668 compliance** — Ubuntu 24.04's "externally managed" Python marker removed to allow system-wide `uv pip install`.
- **Docker: smoke test** — CI test replaced HTTP health check (requires GPU) with static image content verification.
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

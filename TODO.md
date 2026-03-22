# ComfyUI Auto-Installer - TODO / Roadmap

> **Context:** This TODO was assembled during an infrastructure review.
> Updated 2026-03-21 — reflects the Python rewrite status.

---

## 1. Security

### ~~1.1 Network Exposure - `--listen` binds 0.0.0.0~~ ✅
> **Done:** `InstallerSettings.listen_address` defaults to `127.0.0.1`. Generated launchers use the setting.

### ~~1.2 Supply Chain - No Checksum Verification~~ ✅
> **Done:** SHA-256 checksums on all tools and wheels in `dependencies.json`. `download_file()` verifies checksums. All URLs point to HuggingFace Assets (primary) with ModelScope fallback.

### ~~1.3 Raw `pip` Usage~~ ✅
> **Done:** All package operations use `uv`. No pip calls remain.

### ~~1.4 DazzleML Script~~ ✅
> **Done:** Completely replaced. Direct wheel installs from PyPI/GitHub Releases with version mapping in `src/installer/optimizations.py`.

### ~~1.5 `Invoke-Expression` with Dynamic Strings~~ ✅
> **Done:** PowerShell scripts eliminated entirely. Python rewrite uses `subprocess.run()` with explicit argument lists.

### ~~1.6 Bootstrap Overwrites User Config~~ ✅
> **Done:** `InstallerSettings` (`local-config.json`) is never overwritten. Bootstrap creates from defaults only if missing.

### ~~1.7 `repo-config.json`~~ ✅
> **Done:** Folded into `InstallerSettings` (`gh_user`, `gh_reponame`, `gh_branch`). Old file deprecated.

### ~~1.8 Pickle/Tensor Model Scanner~~ ✅
> **Done:** `picklescan` dependency added. Scanner utility in `src/utils/model_scanner.py` detects malicious pickle code in `.ckpt`/`.pt`/`.pth` files. CLI command `scan-models` with Rich table output. Non-blocking warning integrated into update flow (step 5/5). 17 unit tests.

### ~~1.9 Admin Privilege Audit~~ ✅
> **Done:** Python rewrite requires zero admin elevation. Long paths enabled via registry user-level, VS Build Tools detected via `vswhere`.

---

## 2. Package Management

### ~~2.1 UV as Default Package Manager~~ ✅
> **Done:** `uv` is the sole package manager. Venv creation, installs, and editable installs all use `uv`.

### ~~2.2 Legacy Migration Path~~ → Not Needed
> **Rationale:** `python-rewrite` creates a fresh install — it does not upgrade existing PowerShell-based installs in-place. Users should do a clean install. No migration code required.

### ~~2.3 Constraints File Support~~ → Removed
> **Rationale:** `uv` handles dependency resolution natively and reliably. No user has ever requested this. Removing to reduce scope.

---

## ~~3. DazzleML Replacement~~ ✅

> **Done:** Entirely replaced by `src/installer/optimizations.py` — direct installs of SageAttention + triton-windows from PyPI.

### ~~3.1~~ ✅ Direct wheel install implemented
### ~~3.2~~ ✅ VS Build Tools optional — only needed for insightface source build
### ~~3.3~~ ✅ Compiler toolchain detection via vswhere
### ~~3.4 Track astral-sh Pyx~~ → Removed
> **Rationale:** Informational only, not actionable. Will be picked up naturally when/if Pyx ships.

---

## 4. Dependency Conflicts and Deprecation

### ~~4.1 `pynvml` vs `nvidia-ml-py` Conflict~~ ✅
> **Done:** `pynvml` removed from `dependencies.json`.

### ~~4.2 Deprecation Warnings Audit~~ → Removed
> **Rationale:** Cosmetic only, no user impact. Python rewrite uses modern APIs throughout. If warnings surface, they'll come from upstream dependencies and should be fixed there.

### ~~4.3 `custom_nodes.csv` - Dead Code~~ ✅
> **Done:** Replaced by `custom_nodes.json` manifest with additive-only logic.

---

## ~~5. Configuration Architecture~~ ✅

> **Done:** `InstallerSettings` (Pydantic model) loaded from/saved to `local-config.json`. Bootstrap creates only if missing. Contains: listen_address, listen_port, install_type, package_manager, gh_user, etc.

---

## 6. Reliability and Error Handling

### ~~6.1 Junction Creation - Unchecked~~ ✅
> **Done:** Python junction creation (`_create_junction()` in `install.py`) checks `os.path.isdir()` and raises on failure.

### ~~6.2 `SilentlyContinue` Hiding Failures~~ ✅
> **Done:** PowerShell eliminated. Python uses explicit error handling with `InstallerFatalError`.

### ~~6.3 Git Pull - No Conflict Handling~~ ✅
> **Done:** `run_and_log()` in `updater.py` uses `git pull --rebase --autostash` with proper error capture.

### ~~6.4 `Save-File` Assumes Existing Files Valid~~ ✅
> **Done:** `download_file()` checksums all downloads. Existing files re-verified.

### ~~6.5 CUDA Version Verification~~ ✅
> **Done:** `gpu.py` detects driver version, maps to maximum supported CUDA version, and `install.py` validates it against `dependencies.json`'s supported lists (including AMD ROCm/DirectML targets), offering intelligent fallbacks.

---

## ~~7. Code Quality~~ ✅

> **Done:** Python rewrite addressed all items — no more hardcoded paths, no `Invoke-Expression`, proper `subprocess.run()` with argument arrays, enums replace magic strings.

---

## 8. Documentation

- [x] ~~Document `repo-config.json`~~ → folded into InstallerSettings
- [x] ~~Document listen address~~ → defaults to 127.0.0.1
- [x] ~~Document UV migration~~ → UV is default, no migration needed
- [x] ~~Document compiler toolchain options~~ → insightface removed from custom wheels, built from source via uv automatically
- [x] Add security policy (`SECURITY.md`)
- [x] ~~Document junction architecture~~ → in CONTRIBUTING.md
- [x] ~~CONTRIBUTING.md created~~

---

## 9. Testing

- [x] CI test matrix: Ubuntu + Windows, Python 3.11/3.12/3.13 (6 test jobs)
- [x] CI coverage threshold (`--fail-under=70`) on Ubuntu + Windows
- [x] Node.js 24 migration prep (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`)
- [x] CLI smoke tests (`test_cli_smoke.py`)
- [x] SHA-256 config tests (`test_config.py`)
- [x] Enum tests (`test_enums.py`)
- [x] Python version detection tests (`test_python_info.py`)
- [x] Integration test: full install in CI (Windows VM)
- [x] Validate all checksums in CI (download + verify)
- [x] Docker build & smoke test in CI (ubuntu-latest)
- ~~[ ] Pester test suite~~ → Removed — PowerShell scripts eliminated

---

## 10. Future Features

### ~~10.1 Container Support~~ ✅
> **Done:** Full Docker support with CUDA 13.0 runtime, GHCR auto-publishing, cloud variant with JupyterLab, configurable node tiers, CI build verification for both variants.
- [x] Dockerfile + docker-compose.yml
- [x] NVIDIA Container Toolkit support
- [x] Volume mapping for models/outputs
- [x] `--skip-nodes` flag for lightweight builds
- [x] `.dockerignore` for fast context transfer
- [x] Linux wheel compatibility (skip win_amd64 wheels)
- [x] Docker CI smoke test in GitHub Actions
- [x] `NODE_TIER` env var for custom node bundle selection
- [x] Cloud variant with JupyterLab (`--build-arg VARIANT=cloud`)
- [x] GHCR auto-publish workflow (`docker-publish.yml`)
- [x] `--nodes` flag added to `update` CLI command

### ~~10.2 CI/CD Pipeline~~ ✅
> **Done:** Full CI matrix with lint, security audit, tests, coverage, Windows E2E, Docker smoke test, GHCR publishing.
- [x] CI matrix: Ubuntu + Windows × Python 3.11/3.12/3.13
- [x] Coverage threshold enforcement (70%)
- [x] Automated testing on fresh Windows VMs (full install smoke test)
- [x] Docker build & smoke test (ubuntu-latest)
- [x] GHCR auto-publish on version tags

### ~~10.3 CI Release Automation~~ ✅
> **Done:** `release.yml` workflow triggered on `v*` tags — runs tests, builds sdist/wheel, publishes to PyPI via Trusted Publishing (OIDC), and creates GitHub Release with changelog notes and dist artifacts.
- [x] `release.yml` workflow — triggered on `v*` tags
- [x] Extract changelog section for the tag
- [x] Create GitHub Release with release notes
- [x] PyPI publish via Trusted Publishing (OIDC)

### ~~10.5 SageAttention CI~~ ✅
> **Done:** `build-sageattention.yml` workflow compiles SA2 (v2.2.0, `8.0+PTX`, Python 3.11/3.12/3.13) and SA3 (v1.0.0, sm_100 Blackwell). Wheels uploaded to HuggingFace Assets with automated manifest update. OOM resolved via single-arch + `MAX_JOBS=1`.
- [x] SA2 wheel builds (3 Python versions × sm_80+PTX)
- [x] SA3 Blackwell wheel build (Python 3.13 × sm_100)
- [x] Automated `tools_manifest.json` update with SHA256
- [x] `dependencies.json` updated with correct wheel URLs and checksums

### ~~10.6 Docker Lite Variant~~ ✅
> **Done:** `VARIANT=lite` and `VARIANT=lite-cloud` produce ~2 GB images without pre-installed PyTorch. Entrypoint auto-detects missing venv and runs full install on first boot. Cached in persistent volume for instant subsequent boots.
- [x] Conditional `VARIANT` in Dockerfile (skip PyTorch install)
- [x] Entrypoint first-run detection (`! -d /app/scripts/venv`)
- [x] Docker publish workflow builds all 4 variants
- [x] JupyterLab bash default + trash disabled
- [x] Base image optimized (cuDNN removed)

### ~~10.4 macOS Support~~ ✅
> **Done:** `MacOSPlatform` implemented. Native MPS/CPU handled automatically without CUDA contamination. Badge added to README. Tests added.

### ~~10.5 `--dry-run` Mode~~ → Removed
> **Rationale:** No user demand. The `--yes` flag + `--verbose` provides sufficient visibility into what the installer does. Removing to reduce scope.

---

## Priority Order (Updated 2026-03-22)

**All items completed.** ✅ The project is release-ready.

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

### 1.8 Pickle/Tensor Model Scanner
- **Status:** Not yet implemented.
- **Priority:** Low — `.safetensors` is safe by design, only `.ckpt`/`.pt` files are risky. The model catalog only distributes `.safetensors`.
- **Action:** Monitor for upstream scanner libs. Consider adding a warning if users manually download `.ckpt` files.

### ~~1.9 Admin Privilege Audit~~ ✅
> **Done:** Python rewrite requires zero admin elevation. Long paths enabled via registry user-level, VS Build Tools detected via `vswhere`.

---

## 2. Package Management

### ~~2.1 UV as Default Package Manager~~ ✅
> **Done:** `uv` is the sole package manager. Venv creation, installs, and editable installs all use `uv`.

### 2.2 Legacy Migration Path
- **Status:** Not yet needed — `python-rewrite` is a fresh install path, no existing pip venvs to migrate.
- **Priority:** Medium — needed before merging to `main` if existing users upgrade.
- **Action:** Add upgrade detection in `run_install()` to handle existing pip-based venvs.

### 2.3 Constraints File Support
- **Status:** Not yet implemented.
- **Priority:** Low — `uv` handles dependency resolution well. Feature for power users.

---

## ~~3. DazzleML Replacement~~ ✅

> **Done:** Entirely replaced by `src/installer/optimizations.py` — direct installs of SageAttention + triton-windows from PyPI.

### ~~3.1~~ ✅ Direct wheel install implemented
### ~~3.2~~ ✅ VS Build Tools optional — only needed for insightface source build
### ~~3.3~~ ✅ Compiler toolchain detection via vswhere
### 3.4 Track astral-sh Pyx
- **Status:** Monitoring. Not actionable until Pyx ships.

---

## 4. Dependency Conflicts and Deprecation

### ~~4.1 `pynvml` vs `nvidia-ml-py` Conflict~~ ✅
> **Done:** `pynvml` removed from `dependencies.json`.

### 4.2 Deprecation Warnings Audit
- **Status:** Pending. Need to run a full install and capture `DeprecationWarning`s.
- **Priority:** Low — cosmetic impact only.

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
- [ ] Document compiler toolchain options (for insightface source build)
- [x] Add security policy (`SECURITY.md`)
- [x] ~~Document junction architecture~~ → in CONTRIBUTING.md
- [x] ~~CONTRIBUTING.md created~~

---

## 9. Testing

- [x] CI test matrix: Ubuntu + Windows, Python 3.11/3.12/3.13 (6 test jobs)
- [x] CI coverage threshold (`--fail-under=50`) on Ubuntu + Windows
- [x] Node.js 24 migration prep (`FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`)
- [x] CLI smoke tests (`test_cli_smoke.py`)
- [x] SHA-256 config tests (`test_config.py`)
- [x] Enum tests (`test_enums.py`)
- [x] Python version detection tests (`test_python_info.py`)
- [ ] Integration test: full install in CI (Windows VM)
- [ ] Validate all checksums in CI (download + verify)
- ~~[ ] Pester test suite~~ → Removed — PowerShell scripts eliminated

---

## 10. Future Features

### 10.1 Container Support
- **Priority:** Low — primary target is desktop users.
- [ ] Dockerfile + docker-compose.yml
- [ ] NVIDIA Container Toolkit support
- [ ] Volume mapping for models/outputs

### 10.2 CI/CD Pipeline
- [x] CI matrix: Ubuntu + Windows × Python 3.11/3.12/3.13
- [x] Coverage threshold enforcement (50%)
- [ ] Automated testing on fresh Windows VMs (full install smoke test)

### ~~10.3 Release Signing~~ → Deferred
> Not applicable — no releases published. Installation via git clone / one-liner.

### ~~10.4 macOS Support~~ ✅
> **Done:** `MacOSPlatform` implemented. Native MPS/CPU handled automatically without CUDA contamination. Badge added to README. Tests added.

### 10.5 `--dry-run` Mode
- **Priority:** Low — deferred for later.

---

## Priority Order (Updated)

1. **Integration test in CI** — full install on Windows VM (§9)
2. **Container support** — for advanced users (§10.1)
3. **Constraints file** — power user feature (§2.3)
4. **Deprecation audit** — cosmetic (§4.2)

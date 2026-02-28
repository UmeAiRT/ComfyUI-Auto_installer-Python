# ComfyUI Auto-Installer — Agent Development Guide

> Instructions for AI coding agents working on this project.
> For architecture details, see `/docs/codemaps/`.
>
> This file follows the [AGENTS.md](https://agents.md) standard.

## Project Overview

Cross-platform Python CLI installer for ComfyUI. Automates: Python environment setup (venv/conda), ComfyUI cloning, custom node installation, GPU optimization (Triton/SageAttention), and model downloads. Key characteristic: **junction-based architecture** keeps user data separate from the ComfyUI git repo for clean updates.

## Build / Test / Run

```bash
# Setup development environment
pip install -e .

# Run tests
pytest tests/ -q

# Run the installer
comfyui-installer install --path C:\path\to\install --type venv

# Run with verbose output
comfyui-installer install --path C:\path\to\install -v
```

## Architecture

### Two-Phase Installation

| Phase | File | Purpose |
|-------|------|---------|
| **Phase 1** | `src/installer/phase1.py` | System checks, Python detection, venv/conda setup, tool installs (aria2, uv, git) |
| **Phase 2** | `src/installer/phase2.py` | ComfyUI clone, junctions, pip packages, custom nodes, wheels, optimizations, launcher generation |

### Junction-Based Architecture

**Never modify ComfyUI core folders directly.** User data (models, outputs, custom nodes) lives in external folders, linked into ComfyUI via junctions. This allows `git pull` updates without data loss.

```python
# CORRECT - Use junction architecture
junction_dirs = ["models", "output", "input", "user"]
for dirname in junction_dirs:
    external = install_path / dirname       # User data
    comfy_target = comfy_path / dirname     # Junction inside ComfyUI/
    create_junction(external, comfy_target)

# WRONG - Putting files directly in ComfyUI/
shutil.copy(model, comfy_path / "models" / "file.safetensors")
```

### Custom Nodes: Additive-Only Manifest

Nodes are managed via `scripts/custom_nodes.json` (not ComfyUI-Manager snapshots).

```python
# CORRECT - Add to custom_nodes.json
{
    "name": "ComfyUI-NewNode",
    "url": "https://github.com/user/ComfyUI-NewNode",
    "requirements": "requirements.txt"
}

# WRONG - Use snapshot.json or manual git clone
```

**Rules:**

- Never remove user-installed nodes (additive only)
- Always specify `requirements` if the node has a `requirements.txt`
- Use `required: true` only for essential nodes (Manager, Sync)

## Critical Conventions

### Security First

This is an installer that downloads and executes code. Security is critical.

- **No external script execution**: Never download `.py` files from the internet and execute them
- **Subprocess safety**: Always use `subprocess.run()` with explicit argument lists (no `shell=True`)
- **HTTPS only**: All URLs must use HTTPS
- **No `eval`/`exec`**: Never use dynamic code execution with external input

### Logging System

```python
from src.utils.logging import InstallerLogger

log.step("Step Title")          # Level 0 — Increments step counter [Step X/N]
log.item("Main task info")      # Level 1 — Bullet point with →
log.sub("Sub-detail")           # Level 2 — Indented sub-item with →
log.info("Verbose detail")      # Level 3 — Hidden by default (shown with -v)
log.success("Done!", level=1)   # Green success message
log.error("Failed!")            # Red error message
```

**Important:**

- `log.step()` auto-increments the step counter — use exactly once per installation phase
- `log.info()` (level 3) is hidden from console unless `--verbose` is enabled
- Log to file always includes all levels regardless of verbose setting

### Command Execution

```python
from src.utils.commands import run_and_log, CommandError

# CORRECT - Use run_and_log for subprocess calls
try:
    run_and_log("git", ["clone", url, str(path)], timeout=300)
except CommandError as e:
    log.error(f"Clone failed: {e}")

# WRONG - Direct subprocess.run without logging
subprocess.run(["git", "clone", url], check=True)
```

### Configuration

All dependencies and URLs are in `scripts/dependencies.json`, validated by Pydantic models in `src/config.py`.

```python
# CORRECT - Add to dependencies.json, define in Pydantic model
deps = load_dependencies(Path("scripts/dependencies.json"))
torch_url = deps.pip_packages.torch.index_url

# WRONG - Hardcode URLs in Python code
torch_url = "https://download.pytorch.org/whl/cu130"
```

## File Structure

| Path | Purpose |
|------|---------|
| `src/cli.py` | Typer CLI entry point (install, update, download-models, info) |
| `src/config.py` | Pydantic models for `dependencies.json` and user settings |
| `src/installer/phase1.py` | Phase 1: system setup, Python, environment |
| `src/installer/phase2.py` | Phase 2: ComfyUI, nodes, packages, launchers |
| `src/installer/updater.py` | Update logic (git pull + node updates) |
| `src/installer/nodes.py` | Custom node management (additive manifest) |
| `src/utils/logging.py` | `InstallerLogger` with step counter and verbose mode |
| `src/utils/commands.py` | `run_and_log()`, `check_command_exists()` |
| `src/utils/download.py` | Download with aria2c/urllib fallback |
| `src/utils/gpu.py` | GPU detection, VRAM info |
| `src/platform/` | Cross-platform abstractions (Windows/Linux) |
| `src/downloader/engine.py` | Model catalog download system |
| `scripts/dependencies.json` | URLs, packages, tools config |
| `scripts/custom_nodes.json` | Node manifest (additive only) |
| `scripts/nunchaku_versions.json` | Version matrix for nunchaku node |
| `Install.bat` / `Install.sh` | Bootstrap entry points for users |
| `bootstrap/` | Legacy bootstrap scripts |
| `tests/` | pytest test suite |

## Critical Files

| File | Notes |
|------|-------|
| `scripts/dependencies.json` | All URLs must be HTTPS. PyTorch index URL must match version. |
| `scripts/custom_nodes.json` | Additive only. Never remove entries. |
| `src/__init__.py` | Contains `__version__` — bump on every release. |
| `src/utils/logging.py` | Changes affect all installer output. Test verbose/non-verbose. |

## Common Pitfalls

| Don't | Do Instead |
|-------|-----------|
| Download and execute external scripts | Internalize the logic and credit the source |
| Use `log.sub()` for command output | Use `log.info()` — hidden by default |
| Hardcode paths or URLs | Use `dependencies.json` + Pydantic config |
| Call `log.step()` more than once per phase | Count steps carefully — it increments the counter |
| Forget to update `total_steps` in `phase1.py` | Count all `log.step()` calls across phase1 + phase2 |
| Put files in `ComfyUI/` directly | Use junction architecture (external folders) |
| Use `shell=True` in subprocess | Use explicit argument lists via `run_and_log()` |

## Adding New Features

**New Custom Node:**

1. Add entry to `scripts/custom_nodes.json` with `name`, `url`, and optionally `requirements`
2. Test with fresh install (`--path` to a clean directory)
3. Verify in both verbose and non-verbose modes

**New Dependency:**

1. Add to `scripts/dependencies.json` under the correct section
2. Update Pydantic model in `src/config.py` if adding a new field
3. Update tests if needed
4. Test install order (some packages depend on others)

**New Installation Step:**

1. Add function to `phase2.py`
2. Call it from `run_phase2()` in the correct order
3. **Increment `total_steps`** in `phase1.py`
4. Test step counter displays correctly

**New CLI Command:**

1. Add to `src/cli.py` with `@app.command()`
2. Follow existing pattern for options (`--path`, `--verbose`)
3. Update this AGENTS.md

## 🚨 Mandatory Verification Checklist

**Before marking any task as complete, you MUST verify:**

1. [ ] **Tests pass**: `pytest tests/ -q` — all tests green
2. [ ] **Step counter**: `total_steps` in `phase1.py` matches actual `log.step()` calls
3. [ ] **Verbose mode**: No `[INFO]` leaking in non-verbose mode
4. [ ] **No hardcoded paths**: Use config or path arguments
5. [ ] **Dependencies**: New packages added to both `dependencies.json` and Pydantic models

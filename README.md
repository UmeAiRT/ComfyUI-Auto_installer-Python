# 🚀 UmeAiRT's ComfyUI Auto-Installer

![Version](https://img.shields.io/badge/Version-5.0.0--alpha.3-orange.svg)
![Python](https://img.shields.io/badge/Python-3.11%20|%203.12%20|%203.13-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS%20%7C%20Docker-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Tests](https://img.shields.io/badge/Tests-406%20passed-brightgreen.svg)

Cross-platform Python CLI to fully automate the installation, update, and configuration of ComfyUI. One-click setup with GPU optimizations, curated custom nodes, and VRAM-aware model downloads.

## ✨ Features

- **One-Click Install** — Double-click `Install.bat` (Windows) or run `Install.sh` (Linux/macOS)
- **Isolated Core** — The installer runs in its own dedicated, safe virtual environment (`.installer_venv`).
- **Cross-Platform Compatibility**:
  - **Windows**: Full support for NVIDIA (CUDA), AMD (DirectML), and CPU-only fallbacks.
  - **Linux**: Full support for NVIDIA (CUDA), AMD (ROCm), and CPU-only fallbacks.
  - **macOS**: Full support leveraging Apple Silicon (MPS).
- **Flexible Installations**: Supports both `uv` Virtual Environments (`venv`) and Git-tracked `conda`/`venv` integration.
- **GPU Optimizations** — Installs Triton, SageAttention, and xformers with version compatibility
- **34 Curated Custom Nodes** — Additive manifest system — never removes user-installed nodes
- **Model Catalog v3** — 7 model families (FLUX, Z-IMAGE, WAN 2.1, WAN 2.2, HiDream, QWEN, LTX-2) with VRAM-based recommendations and SHA-256 integrity
- **Multi-Source Downloads** — aria2c accelerated, with HuggingFace + ModelScope fallback
- **Junction Architecture** — User data (models, outputs) persists independently from ComfyUI updates
- **Smart Update** — One command to update ComfyUI core, all bundled nodes, and Python dependencies
- **Model Security Scanner** — Detects malicious pickle code in `.ckpt`/`.pt` model files using `picklescan`
- **Cross-Platform Launchers** — Generated `.bat`/`.sh` scripts (Performance, LowVRAM, Update, Download)
- **Verbose Mode** — Clean output by default, detailed logging with `-v` flag

## 📋 Prerequisites

- **Git**
- **GPU:** NVIDIA (CUDA 12.x+), AMD (Radeon RX 6000+), or Apple Silicon (M1+)
- **Internet connection**
- **[Optional] C++ Compiler:** Windows users might need [Visual Studio Build Tools](https://aka.ms/vs/17/release/vs_BuildTools.exe) (C++ workload) if installing custom nodes that require source compilation (e.g., `insightface`). Linux/macOS users usually have `gcc`/`clang` installed by default.

> **Note:** Python 3.13 is auto-installed via `uv` if not present. No manual Python setup required.

## 🏁 Quick Start

### Option A: One-Liner (Recommended)

**Windows** (PowerShell):
```powershell
irm https://get.umeai.art/comfyui.ps1 | iex
```

**Linux / macOS**:
```bash
curl -fsSL https://get.umeai.art/comfyui.sh | sh
```

> Only requires **Git** — everything else (Python, uv, dependencies) is handled automatically.

### Option B: Manual Download

1. Download or clone this repository
2. Double-click **`Install.bat`** (Windows) or run `./Install.sh` (Linux/macOS)
3. Follow the on-screen prompts (install type, model packs)
4. When done, double-click **`UmeAiRT-Start-ComfyUI.bat`** to launch!

### Option C: CLI (Advanced)

```bash
# Install the CLI tool
pip install -e .

# Run the installer
umeairt-comfyui-installer install --path /path/to/install --type venv

# With verbose output
umeairt-comfyui-installer install --path /path/to/install -v
```

### Option D: Docker Container

Requires [Docker](https://www.docker.com/products/docker-desktop/) and an NVIDIA GPU.

```bash
docker run --gpus all -p 8188:8188 -v comfyui-data:/data -e NODE_TIER=full ghcr.io/umeairt/comfyui:latest
```

Open **http://localhost:8188** — done! ✅

All your data (models, nodes, outputs) is stored in the `comfyui-data` volume and persists between restarts. To use a local folder instead: replace `comfyui-data:/data` with `./comfyui_data:/data`.

**Available image variants:**

| Tag | Size | Description |
|-----|------|-------------|
| `latest` | ~4 GB | ComfyUI with pre-installed PyTorch (ready to go) |
| `latest-cloud` | ~4.5 GB | + JupyterLab for RunPod / cloud |
| `latest-lite` | ~2 GB | Minimal — installs PyTorch on first run (~5 min) |
| `latest-lite-cloud` | ~2 GB | Lite + JupyterLab |

**Cloud variant** (with JupyterLab for RunPod / remote):

```bash
docker run --gpus all --name comfyui -p 8188:8188 -p 8888:8888 -v comfyui-data:/data -e JUPYTER_ENABLE=true -e NODE_TIER=umeairt ghcr.io/umeairt/comfyui:latest-cloud
```

> **Tip:** Use `-e NODE_TIER=minimal`, `umeairt`, or `full` (default) to control which custom nodes are installed on boot. The **lite** variants are ideal for RunPod where fast image pulls matter — PyTorch installs once on first boot and is cached in the persistent volume.

## 📂 Post-Installation

Four launcher scripts are generated in your install directory:

| Script | Description |
|--------|-------------|
| `UmeAiRT-Start-ComfyUI.bat/.sh` | Launch ComfyUI (Performance mode with SageAttention) |
| `UmeAiRT-Start-ComfyUI_LowVRAM.bat/.sh` | Launch with `--lowvram --fp8` for ≤8 GB VRAM GPUs |
| `UmeAiRT-Download-Models.bat/.sh` | Reopen the model download menu |
| `UmeAiRT-Update.bat/.sh` | Update ComfyUI, custom nodes, and dependencies |

## 🛠️ CLI Commands

```bash
umeairt-comfyui-installer install            # Full installation
umeairt-comfyui-installer update             # Update ComfyUI + nodes + deps
umeairt-comfyui-installer download-models    # Interactive model downloads
umeairt-comfyui-installer scan-models        # Scan models for malicious pickle code
umeairt-comfyui-installer info               # Display system info (GPU, Python, tools)
umeairt-comfyui-installer version            # Show version
```

All commands support `--path` (install directory) and `--verbose` flags.

## 📁 Architecture

### Project Structure

```
ComfyUI-Auto_installer/
├── src/
│   ├── cli.py                # Typer CLI entry point
│   ├── config.py             # Pydantic config models
│   ├── installer/            # Install, update, nodes, finalize
│   │   ├── templates/        # .bat/.sh launcher templates
│   │   └── ...
│   ├── downloader/           # Model download engine (manifest v3)
│   ├── platform/             # OS abstraction (Windows/Linux/macOS)
│   └── utils/                # Logging, commands, packaging, GPU detection
├── scripts/                  # Config files (dependencies.json, custom_nodes.json)
├── tests/                    # 406 tests (unit + integration)
├── Install.bat / Install.sh  # Bootstrap entry points
└── pyproject.toml            # Project metadata (hatchling)
```

### Install Directory Layout

The installer uses a **junction-based architecture** to separate user data from ComfyUI core:

```
install_path/
├── scripts/venv/            # Python virtual environment (venv or conda)
├── ComfyUI/                 # Git repo (can be wiped for updates)
│   ├── models/ → ../models  # ← junction (symlink)
│   ├── output/ → ../output  # ← junction
│   └── main.py
├── models/                  # ← User data (persists)
├── output/                  # ← User data (persists)
├── logs/                    # Install and update logs
├── scripts/                 # Venv, config files, install metadata
├── UmeAiRT-Start-ComfyUI.bat
├── UmeAiRT-Update.bat
└── UmeAiRT-Download-Models.bat
```

### Model Catalog (v3)

Models are defined in `model_manifest.json`, fetched from the [Assets repository](https://huggingface.co/UmeAiRT/ComfyUI-Auto-Installer-Assets) at install/update time:

| Family | Bundles | Type |
|--------|---------|------|
| **FLUX** | Dev, Fill | Image |
| **Z-IMAGE** | Turbo | Image |
| **WAN 2.1** | T2V, I2V 480p | Video |
| **WAN 2.2** | I2V, Fun Inpaint, Fun Camera | Video |
| **HiDream** | Dev | Image |
| **QWEN** | Image Edit | Image |
| **LTX-2** | Dev | Video + Audio |

Each bundle offers multiple quantization variants (fp16, fp8, GGUF Q3→Q8) with VRAM recommendations (★ markers) and SHA-256 integrity checks. Downloads are accelerated via aria2c with HuggingFace + ModelScope fallback.

## 🧑‍💻 Contributing

Contributions are welcome! See [`AGENTS.md`](AGENTS.md) for development guidelines and [`docs/codemaps/`](docs/codemaps/) for architecture diagrams.

```bash
# Setup development environment
uv sync --dev

# Run tests
uv run pytest tests/ -q

# Lint
uv run ruff check src/ tests/
```

## 📜 Third-Party Code & Attribution

| Component | Source | License |
|:---|:---|:---|
| Triton/SageAttention install logic | [DazzleML/comfyui-triton-and-sageattention-installer](https://github.com/DazzleML/comfyui-triton-and-sageattention-installer) | MIT |
| ComfyUI | [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI) | GPL-3.0 |

## 🔒 Security

- **No external script execution** — all installation logic is internalized
- **Secure subprocess calls** — no `shell=True`, explicit argument lists
- **HTTPS only** — all download URLs validated
- **Automated audits** — CI runs Bandit + pip-audit on every push
- **Pickle model scanner** — Detects malicious code in `.ckpt`/`.pt` files via `picklescan` (auto-runs during updates)
- **Zip slip prevention** — Archive extraction validates all paths stay within the target directory
- **SHA-256 integrity** — Post-download checksum verification for all model files

For details, see [`SECURITY.md`](SECURITY.md).

## 📝 License

MIT License — see [`LICENSE`](LICENSE) file.

## ❤️ Credits

Developed by **UmeAiRT**.
Thanks to **Comfyanonymous** for creating ComfyUI and to all custom node authors.

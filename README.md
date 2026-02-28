# 🚀 UmeAiRT's ComfyUI Auto-Installer

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Cross-platform Python CLI to fully automate the installation and configuration of ComfyUI. One-click setup with GPU optimizations, curated custom nodes, and model downloads.

## ✨ Features

- **One-Click Install** — Double-click `Install.bat` (Windows) or run `Install.sh` (Linux/macOS)
- **Smart Environment** — Auto-detects system, creates venv or conda environment
- **GPU Optimizations** — Installs Triton, SageAttention, and xformers with version compatibility
- **Curated Custom Nodes** — 30+ essential nodes installed via additive manifest (never removes user-installed nodes)
- **Model Downloads** — Interactive menu with VRAM-based recommendations (FLUX, WAN, HiDream, LTX, QWEN)
- **Junction Architecture** — User data (models, outputs) persists independently from ComfyUI updates
- **Auto-Update** — Update ComfyUI, nodes, and dependencies with one command
- **Cross-Platform Launchers** — Generated at install time (Performance, LowVRAM, Update, Download Models)
- **Verbose Mode** — Clean output by default, detailed logging with `-v` flag

## 📋 Prerequisites

- **Python 3.13** (with `pip`)
- **Git**
- **NVIDIA GPU** with CUDA 13.0+ drivers
- Internet connection

## 🏁 Quick Start

### Option A: For Users (Beginners)

1. Download or clone this repository
2. Double-click **`Install.bat`** (Windows) or run `./Install.sh` (Linux/macOS)
3. Follow the on-screen instructions
4. When done, double-click **`UmeAiRT-Start-ComfyUI.bat`** to launch!

### Option B: CLI (Advanced)

```bash
# Install the CLI tool
pip install -e .

# Run the installer
comfyui-installer install --path C:\path\to\install --type venv

# With verbose output
comfyui-installer install --path C:\path\to\install -v
```

## 📂 Post-Installation

Four launcher scripts are generated in your install directory:

| Script | Description |
|--------|-------------|
| `UmeAiRT-Start-ComfyUI.bat/.sh` | Launch ComfyUI (Performance mode with SageAttention) |
| `UmeAiRT-Start-ComfyUI_LowVRAM.bat/.sh` | Launch with memory optimizations for low VRAM GPUs |
| `UmeAiRT-Download-Models.bat/.sh` | Reopen the model download menu |
| `UmeAiRT-Update.bat/.sh` | Update ComfyUI, custom nodes, and dependencies |

## 🛠️ CLI Commands

```bash
comfyui-installer install            # Full installation
comfyui-installer update             # Update everything
comfyui-installer download-models    # Interactive model downloads
comfyui-installer info               # Display system info (GPU, Python, tools)
comfyui-installer version            # Show version
```

## 📁 Architecture

The installer uses a **junction-based architecture** to separate user data from ComfyUI core:

```
install_path/
├── ComfyUI/                 # Git repo (can be wiped for updates)
│   ├── models/ → ../models  # ← junction (symlink)
│   ├── output/ → ../output  # ← junction
│   └── main.py
├── models/                  # ← User data (persists)
├── output/                  # ← User data (persists)
├── scripts/                 # Config files
├── UmeAiRT-Start-ComfyUI.bat
└── UmeAiRT-Update.bat
```

## 🧑‍💻 Contributing

Contributions are welcome! See [`AGENTS.md`](AGENTS.md) for development guidelines and [`docs/codemaps/`](docs/codemaps/) for architecture diagrams.

```bash
# Setup development environment
pip install -e .

# Run tests
pytest tests/ -q
```

## 📜 Third-Party Code & Attribution

This project uses or is inspired by the following open-source projects:

| Component | Source | License |
|:---|:---|:---|
| Triton/SageAttention install logic | [DazzleML/comfyui-triton-and-sageattention-installer](https://github.com/DazzleML/comfyui-triton-and-sageattention-installer) | MIT |
| ComfyUI | [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI) | GPL-3.0 |

## 🔒 Security

- **No external script execution** — all installation logic is internalized
- **Secure subprocess calls** — no `shell=True`, explicit argument lists
- **HTTPS only** — all download URLs validated
- CVE-2025-69277 patched (path traversal fix)

## 📝 License

MIT License — see [`LICENSE`](LICENSE) file.

## ❤️ Credits

Developed by **UmeAiRT**.
Thanks to **Comfyanonymous** for creating ComfyUI and to all custom node authors.

# Getting Started

## Prerequisites

- **Git** installed
- **GPU:** NVIDIA (CUDA 12.x+), AMD (Radeon RX 6000+), or Apple Silicon (M1+)
- **Internet connection**
- **[Optional]** Visual Studio Build Tools (Windows, for source compilation of some custom nodes)

!!! tip
    Python 3.11–3.13 is auto-installed via `uv` if not present. No manual Python setup required.

## Installation Methods

### Option A: One-Liner (Recommended)

=== "Windows (PowerShell)"

    ```powershell
    irm https://get.umeai.art/comfyui.ps1 | iex
    ```

=== "Linux / macOS"

    ```bash
    curl -fsSL https://get.umeai.art/comfyui.sh | sh
    ```

### Option B: Manual Download

1. Download or clone this repository
2. Double-click **`Install.bat`** (Windows) or run `./Install.sh` (Linux/macOS)
3. Follow the on-screen prompts
4. When done, launch with **`UmeAiRT-Start-ComfyUI.bat`**

### Option C: CLI (Advanced)

```bash
pip install -e .
umeairt-comfyui-installer install --path /path/to/install --type venv
```

### Option D: Docker

```bash
docker run --gpus all -p 8188:8188 -v comfyui:/data ghcr.io/umeairt/comfyui:latest
```

See [Docker](docker.md) for storage options and customization.

## Post-Installation

Three launcher scripts are generated:

| Script | Description |
|--------|-------------|
| `UmeAiRT-Start-ComfyUI` | Launch ComfyUI (Performance mode) |
| `UmeAiRT-Start-ComfyUI_LowVRAM` | Launch with `--lowvram --fp8` for ≤8 GB VRAM |
| `UmeAiRT-Manager` | Open the TUI manager (update, download, reinstall, settings) |

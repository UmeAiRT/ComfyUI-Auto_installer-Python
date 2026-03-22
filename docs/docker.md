# Docker

## Quick Start

Requires [Docker](https://www.docker.com/products/docker-desktop/) and an NVIDIA GPU.

```bash
docker run --gpus all -p 8188:8188 -v comfyui:/data ghcr.io/umeairt/comfyui:latest
```

Open **http://localhost:8188** — ComfyUI is ready.

That's it. All your data (models, custom nodes, outputs) is stored in the `comfyui` volume and persists between container restarts or removal.

!!! tip "Windows"
    Docker Desktop with WSL2 handles GPU passthrough automatically — no extra setup needed with recent NVIDIA drivers (≥ 525.x).

---

## Data Storage

You have two options for where your data lives:

### Option 1: Docker Volume (recommended)

```bash
docker run --gpus all -p 8188:8188 -v comfyui:/data ghcr.io/umeairt/comfyui:latest
```

Docker manages the storage. Data persists until you explicitly delete the volume. Simple and cross-platform.

### Option 2: Local Folder

```bash
docker run --gpus all -p 8188:8188 -v ./comfyui_data:/data ghcr.io/umeairt/comfyui:latest
```

Data lives in `./comfyui_data/` on your disk — you can see and edit the files directly:

```
./comfyui_data/
├── models/          ← drop .safetensors files here
├── custom_nodes/    ← installed automatically at first boot
├── output/          ← your generated images
├── input/           ← images you upload to ComfyUI
└── user/            ← ComfyUI settings
```

!!! note
    If no `-v` is specified, Docker still creates an anonymous volume automatically (thanks to `VOLUME /data` in the Dockerfile), so you won't lose data accidentally — but finding that anonymous volume later is harder.

---

## Customization

### Custom Node Bundles

Control which nodes get installed with the `NODE_TIER` environment variable:

| Tier | What's installed | Use Case |
|------|-----------------|----------|
| `minimal` | ComfyUI-Manager only | Quick testing |
| `umeairt` | + UmeAiRT Sync/Toolkit + essentials | UmeAiRT workflows |
| `full` | + all community nodes (~34) | **Default** |

```bash
docker run --gpus all -p 8188:8188 -v comfyui:/data -e NODE_TIER=minimal ghcr.io/umeairt/comfyui:latest
```

Change tiers by restarting with a different value — no rebuild needed.

### JupyterLab (Cloud / RunPod)

A **cloud variant** adds JupyterLab for remote development:

```bash
docker run --gpus all -p 8188:8188 -p 8888:8888 -v comfyui:/data \
  -e JUPYTER_ENABLE=true -e JUPYTER_TOKEN=mysecrettoken \
  ghcr.io/umeairt/comfyui:latest-cloud
```

- ComfyUI → **:8188**
- JupyterLab → **:8888**

### All Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_TIER` | `full` | Custom node bundle (`minimal`, `umeairt`, `full`) |
| `JUPYTER_ENABLE` | `false` | Start JupyterLab (cloud variant only) |
| `JUPYTER_TOKEN` | *(empty)* | JupyterLab access token |
| `JUPYTER_PORT` | `8888` | JupyterLab listening port |

---

## Docker Compose

If you prefer `docker compose`, clone the repo and use the included `docker-compose.yml`:

```bash
git clone https://github.com/UmeAiRT/ComfyUI-Auto_installer-Python.git
cd ComfyUI-Auto_installer-Python
docker compose up -d
```

Edit `docker-compose.yml` to customize environment variables or switch between Docker volume and local folder storage.

---

## Building Locally

```bash
# Standard image
docker build -t umeairt/comfyui:latest .

# Cloud image (with JupyterLab)
docker build --build-arg VARIANT=cloud -t umeairt/comfyui:cloud .
```

---

## Troubleshooting

### GPU not detected

Verify Docker can see your GPU:

```bash
docker run --rm --gpus all nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04 nvidia-smi
```

### `bash\r: No such file or directory`

Shell scripts have Windows line endings. The Dockerfile fixes this automatically, but if you edited `entrypoint.sh` locally, ensure it uses LF endings.

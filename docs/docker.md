# Docker

The installer provides pre-built Docker images for containerized ComfyUI deployments, available on **GitHub Container Registry**.

## Image Variants

| Image | Tag | Content |
|-------|-----|---------|
| **Standard** | `ghcr.io/umeairt/comfyui:latest` | ComfyUI + PyTorch + CUDA |
| **Cloud** | `ghcr.io/umeairt/comfyui:latest-cloud` | Standard + JupyterLab (for RunPod) |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (for GPU passthrough)

!!! tip
    On **Windows with Docker Desktop**, GPU support works out of the box via WSL2 — no extra installation needed if your NVIDIA driver is recent (≥ 525.x).

## Quick Start

### Pull & Run

```bash
docker pull ghcr.io/umeairt/comfyui:latest
docker run --gpus all -p 8188:8188 ghcr.io/umeairt/comfyui:latest
```

Access ComfyUI at **http://localhost:8188**.

### Docker Compose (Recommended)

Clone the repository and start the stack:

```bash
git clone https://github.com/UmeAiRT/ComfyUI-Auto_installer-Python.git
cd ComfyUI-Auto_installer-Python
docker compose up -d
```

The `docker-compose.yml` maps persistent data to `./docker_data/` on your host.

## Architecture

The Docker setup uses **bind mounts** to persist user data on the host machine. The image itself contains only ComfyUI core + PyTorch — custom nodes are installed into the mounted volumes at container startup.

```
┌─────────────────────────────────────┐
│  Docker Image (build time)          │
│  ✅ Python 3.12, PyTorch, CUDA     │
│  ✅ ComfyUI core, uv, venv         │
│  ❌ No custom nodes                │
└──────────────┬──────────────────────┘
               │  docker run
               ▼
┌─────────────────────────────────────┐
│  Container (runtime)               │
│  1. Reads NODE_TIER env var        │
│  2. Runs "update --nodes $TIER"    │
│  3. Clones nodes into volume       │
│  4. Starts ComfyUI on :8188       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Host (./docker_data/)             │
│  models/  custom_nodes/  output/   │
│  input/   user/                    │
└─────────────────────────────────────┘
```

### Volume Mapping

```yaml
volumes:
  - ./docker_data/models:/app/models
  - ./docker_data/custom_nodes:/app/custom_nodes
  - ./docker_data/output:/app/output
  - ./docker_data/input:/app/input
  - ./docker_data/user:/app/user
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_TIER` | `full` | Custom node bundle (see below) |
| `JUPYTER_ENABLE` | `false` | Start JupyterLab (cloud variant only) |
| `JUPYTER_TOKEN` | *(empty)* | JupyterLab access token |
| `JUPYTER_PORT` | `8888` | JupyterLab listening port |

### Custom Node Bundles

Control which nodes get installed via `NODE_TIER`:

| Tier | Content | Use Case |
|------|---------|----------|
| `minimal` | ComfyUI-Manager only | Quick testing, debugging |
| `umeairt` | + UmeAiRT Sync/Toolkit + essential creative nodes | UmeAiRT workflows |
| `full` | + all community nodes (~34 nodes) | **Default** — complete install |

Each tier is **additive** — it includes all nodes from lower tiers.

```bash
# Run with minimal nodes
docker run --gpus all -e NODE_TIER=minimal -p 8188:8188 ghcr.io/umeairt/comfyui:latest
```

You can change tiers without rebuilding — just restart the container with a different value.

## Cloud Variant (RunPod / Cloud)

The `cloud` image includes **JupyterLab** for remote development and debugging:

```bash
docker run --gpus all \
  -e JUPYTER_ENABLE=true \
  -e JUPYTER_TOKEN=mysecrettoken \
  -p 8188:8188 \
  -p 8888:8888 \
  ghcr.io/umeairt/comfyui:latest-cloud
```

- ComfyUI on **:8188**
- JupyterLab on **:8888**

!!! warning
    Setting `JUPYTER_ENABLE=true` on the **standard** image will show a helpful error message — you need the `cloud` variant for Jupyter.

## Building Locally

```bash
# Standard image
docker build -t umeairt/comfyui:latest .

# Cloud image (with JupyterLab)
docker build --build-arg VARIANT=cloud -t umeairt/comfyui:cloud .

# Rebuild from scratch
docker build --no-cache -t umeairt/comfyui:latest .
```

## Troubleshooting

### `bash\r: No such file or directory`

This happens when shell scripts have Windows line endings (CRLF). The Dockerfile automatically strips them, but if you modified `entrypoint.sh` locally, ensure it uses LF endings.

### GPU not detected

Verify your GPU is visible to Docker:

```bash
docker run --rm --gpus all nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04 nvidia-smi
```

If this doesn't show your GPU, check your NVIDIA driver and Container Toolkit installation.

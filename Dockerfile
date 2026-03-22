# syntax=docker/dockerfile:1.4
# ── Base image: CUDA 13.0 + cuDNN runtime for RTX 50X0 / 40X0 / 30X0 support ──
FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04

# Install system dependencies (Python 3.12 is native to Ubuntu 24.04)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    git \
    build-essential \
    aria2 \
    curl \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Install uv as a standalone binary (matches the bootstrap approach)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -sf /root/.local/bin/uv /usr/local/bin/uv

# Configure workspace
WORKDIR /app

# Create a non-root standard user for security (UID 1000)
# Use a fixed UID/GID so mounted volumes have predictable ownership
# Ubuntu 24.04 already has a group at GID 1000, so use || true for idempotency
RUN (groupadd -g 1000 umeairt || true) && \
    useradd -m -u 1000 -g umeairt umeairt 2>/dev/null || \
    useradd -m -u 1000 -g 1000 umeairt 2>/dev/null || true && \
    chown -R 1000:1000 /app

# Copy the installer repository into the container
COPY --chown=1000:1000 . /app

# Install the installer package system-wide
RUN uv pip install --system -e .

# Switch to non-root user for the build phase
USER umeairt

# Pre-install ComfyUI core during the image build phase.
# This downloads PyTorch with CUDA, installs ComfyUI requirements, and sets up the venv.
# Custom nodes are NOT installed here (--skip-nodes) to keep the image small;
# they are installed at runtime by the entrypoint into the mounted volumes.
RUN python -m src.cli install --path /app --type venv --yes --cuda cu130 --skip-nodes

# Give execution permission to the entrypoint
RUN chmod +x /app/entrypoint.sh

# Expose the standard ComfyUI web port
EXPOSE 8188

# Launch the wrapper
ENTRYPOINT ["/app/entrypoint.sh"]

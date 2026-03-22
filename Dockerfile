# syntax=docker/dockerfile:1.4
# ── Base image: CUDA 13.0 + cuDNN runtime for RTX 50X0 / 40X0 / 30X0 support ──
FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04

# ── Build arguments ──────────────────────────────────────────────
# VARIANT controls the image flavor:
#   standard (default) → ComfyUI only
#   cloud              → ComfyUI + JupyterLab (for RunPod / cloud)
ARG VARIANT=standard

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
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED

# Install uv as a standalone binary (matches the bootstrap approach)
# Copy (not symlink) because /root/.local is inaccessible to non-root users
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv

# Configure workspace
WORKDIR /app

# Ensure /app and /data are owned by UID 1000 (the default non-root user)
# /data is the single persistent volume mount point for all user data.
# Ubuntu 24.04 already ships with a user at UID/GID 1000.
RUN chown -R 1000:1000 /app && mkdir -p /data && chown -R 1000:1000 /data

# Declare /data as a volume so Docker auto-creates one if not explicitly mounted.
# This prevents data loss for users who forget the -v flag.
VOLUME /data

# Copy the installer repository into the container
COPY --chown=1000:1000 . /app

# Install the installer package system-wide
RUN uv pip install --system -e .

# ── Cloud variant: install JupyterLab ────────────────────────────
# Only installed when building with: docker build --build-arg VARIANT=cloud
RUN if [ "$VARIANT" = "cloud" ]; then \
      echo "Installing JupyterLab (cloud variant)..." && \
      uv pip install --system jupyterlab; \
    else \
      echo "Standard variant — skipping JupyterLab."; \
    fi

# Switch to non-root user for the build phase
USER 1000

# Pre-install ComfyUI core during the image build phase.
# This downloads PyTorch with CUDA, installs ComfyUI requirements, and sets up the venv.
# Custom nodes are NOT installed here (--skip-nodes) to keep the image small;
# they are installed at runtime by the entrypoint into the mounted volumes.
RUN python -m src.cli install --path /app --type venv --yes --cuda cu130 --skip-nodes

# Fix line endings (Git on Windows may convert LF→CRLF) and set executable
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Expose ComfyUI (8188) and JupyterLab (8888, cloud variant only)
EXPOSE 8188 8888

# Launch the wrapper
ENTRYPOINT ["/app/entrypoint.sh"]

# syntax=docker/dockerfile:1.4
# ──────────────────────────────────────────────────────────────────
# UmeAiRT ComfyUI Docker Image
#
# Variants (set via --build-arg VARIANT=...):
#   standard      → ComfyUI with pre-installed PyTorch venv (~4 GB)
#   cloud         → standard + JupyterLab
#   lite          → Minimal — installs PyTorch on first run (~1.5 GB)
#   lite-cloud    → lite + JupyterLab
# ──────────────────────────────────────────────────────────────────
FROM nvidia/cuda:13.0.2-runtime-ubuntu24.04

ARG VARIANT=standard

# Install system dependencies in a single layer
# build-essential is only needed for standard/cloud (compilation during install)
# lite variants skip it entirely since PyTorch is installed at runtime from wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3-pip \
    git \
    aria2 \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    && if [ "$VARIANT" = "standard" ] || [ "$VARIANT" = "cloud" ]; then \
         apt-get install -y --no-install-recommends \
           python3.12-dev \
           build-essential; \
       fi \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /usr/lib/python3.12/EXTERNALLY-MANAGED

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && cp /root/.local/bin/uv /usr/local/bin/uv \
    && rm -rf /root/.local/bin

# Install Python 3.13 via uv (for SageAttention 3 Blackwell support)
RUN uv python install 3.13

WORKDIR /app

# Ensure /app and /data are owned by UID 1000
RUN chown -R 1000:1000 /app && mkdir -p /data && chown -R 1000:1000 /data

VOLUME /data

# Copy the installer repository
COPY --chown=1000:1000 . /app

# Install the installer CLI system-wide
RUN uv pip install --system -e .

# Cloud variants: install JupyterLab
RUN if [ "$VARIANT" = "cloud" ] || [ "$VARIANT" = "lite-cloud" ]; then \
      uv pip install --system jupyterlab; \
    fi

USER 1000

# Standard/cloud: pre-install ComfyUI + PyTorch venv during build
# Lite variants: SKIP — the entrypoint handles first-run install
RUN if [ "$VARIANT" = "standard" ] || [ "$VARIANT" = "cloud" ]; then \
      python -m src.cli install --path /app --type venv --yes --cuda cu130 --skip-nodes; \
    fi

# Standard/cloud: remove build tools after compilation (same layer trick:
# we can't do it in the same RUN as install because of USER switch,
# so we accept the small overhead of build-essential in the final image)

# Fix line endings and set executable
USER 0
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh \
    && rm -rf /root/.cache/uv /root/.cache/pip /home/*/.cache/uv /home/*/.cache/pip /tmp/*

USER 1000

EXPOSE 8188 8888

ENTRYPOINT ["/app/entrypoint.sh"]

#!/usr/bin/env bash
set -e

cd /app

# ─── Configuration ──────────────────────────────────────────────
# All settings are controlled via environment variables.
# Set them in docker-compose.yml or with docker run -e KEY=VALUE.

# NODE_TIER controls which custom node bundle gets installed.
# Available tiers (additive — each includes the previous):
#   minimal  → ComfyUI-Manager only (bare minimum)
#   umeairt  → + UmeAiRT Sync/Toolkit + essential creative nodes
#   full     → + all community nodes (default)
NODE_TIER="${NODE_TIER:-full}"

# JupyterLab (cloud variant only — requires --build-arg VARIANT=cloud)
JUPYTER_ENABLE="${JUPYTER_ENABLE:-false}"
JUPYTER_TOKEN="${JUPYTER_TOKEN:-}"
JUPYTER_PORT="${JUPYTER_PORT:-8888}"

# ─── Persistent data (/data volume) ─────────────────────────────
# All user data lives in /data so a single volume mount is enough:
#   docker run -v comfyui:/data ...          (Docker managed volume)
#   docker run -v ./my_data:/data ...        (local folder)
#
# The directories below are created in /data and symlinked into /app
# so ComfyUI finds them where it expects.
DATA_DIRS="models custom_nodes output input user"

for dir in $DATA_DIRS; do
    # Create the directory in /data if it doesn't exist
    mkdir -p "/data/${dir}"

    # Remove the build-time directory (or stale symlink) inside /app
    if [ -L "/app/${dir}" ]; then
        rm "/app/${dir}"
    elif [ -d "/app/${dir}" ]; then
        # Move any build-time content into /data (first boot only)
        if [ "$(ls -A /app/${dir} 2>/dev/null)" ]; then
            cp -rn "/app/${dir}/." "/data/${dir}/" 2>/dev/null || true
        fi
        rm -rf "/app/${dir}"
    fi

    # Create symlink: /app/models → /data/models, etc.
    ln -sfn "/data/${dir}" "/app/${dir}"
done

echo "================================================="
echo "   UmeAiRT ComfyUI — Docker Entrypoint           "
echo "================================================="
echo ""
echo "  Node tier : ${NODE_TIER}"
echo "  Data dir  : /data  ($(du -sh /data 2>/dev/null | cut -f1 || echo 'empty'))"
if [ "$JUPYTER_ENABLE" = "true" ]; then
echo "  Jupyter   : enabled (port ${JUPYTER_PORT})"
fi
echo ""

# ─── Update / install custom nodes ──────────────────────────────
python -m src.cli update --path /app --yes --verbose --nodes "${NODE_TIER}"

# ─── JupyterLab (background) ────────────────────────────────────
if [ "$JUPYTER_ENABLE" = "true" ]; then
    if command -v jupyter &> /dev/null; then
        echo ""
        echo "================================================="
        echo "   Starting JupyterLab on port ${JUPYTER_PORT}..."
        echo "================================================="
        jupyter lab \
            --ip=0.0.0.0 \
            --port="${JUPYTER_PORT}" \
            --no-browser \
            --ServerApp.token="${JUPYTER_TOKEN}" \
            --ServerApp.root_dir=/data &
    else
        echo ""
        echo "⚠️  JUPYTER_ENABLE=true but JupyterLab is not installed."
        echo "   Rebuild with: docker build --build-arg VARIANT=cloud ."
        echo ""
    fi
fi

echo ""
echo "================================================="
echo "   Starting ComfyUI on port 8188...              "
echo "================================================="

# Activate the venv and launch ComfyUI
source /app/scripts/venv/bin/activate
exec python /app/ComfyUI/main.py --listen 0.0.0.0 --port 8188

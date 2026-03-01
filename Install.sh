#!/usr/bin/env bash
# ============================================================================
# UmeAiRT ComfyUI — Auto-Installer
# Run this script to install ComfyUI with all dependencies.
# No prerequisites required — uv handles everything.
# ============================================================================

set -e

echo ""
echo "============================================================================"
echo "          UmeAiRT ComfyUI — Auto-Installer"
echo "============================================================================"
echo ""

# Script location (where bootstrap tools live)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Step 1: Ask for installation path
# ============================================================================
DEFAULT_INSTALL="$HOME/ComfyUI"
echo "Where would you like to install ComfyUI?"
echo "  Default: $DEFAULT_INSTALL"
echo ""
read -rp "Install path (Enter for default): " INSTALL_PATH
INSTALL_PATH="${INSTALL_PATH:-$DEFAULT_INSTALL}"

# Create if it doesn't exist
mkdir -p "$INSTALL_PATH" || {
    echo "[ERROR] Could not create directory: $INSTALL_PATH"
    exit 1
}

echo ""
echo "[INFO] Installation path: $INSTALL_PATH"
echo ""

# ============================================================================
# Step 2: Ensure uv is available
# ============================================================================
if ! command -v uv &>/dev/null; then
    # Check if uv is in our install dir
    if [ -x "$INSTALL_PATH/scripts/uv/uv" ]; then
        export PATH="$INSTALL_PATH/scripts/uv:$PATH"
    else
        echo "[INFO] Installing uv package manager..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"

        if ! command -v uv &>/dev/null; then
            echo "[ERROR] Failed to install uv. Check your internet connection."
            exit 1
        fi
        echo "[INFO] uv installed."
    fi
else
    echo "[INFO] uv already available."
fi

# ============================================================================
# Step 3: Create bootstrap venv (uv auto-downloads Python 3.13 if needed)
# ============================================================================
VENV_PATH="$INSTALL_PATH/scripts/venv"
VENV_PY="$VENV_PATH/bin/python"

if [ ! -f "$VENV_PY" ]; then
    echo "[INFO] Creating Python 3.13 environment..."
    uv venv "$VENV_PATH" --python 3.13 --seed
    echo "[INFO] Python environment ready."
else
    echo "[INFO] Python environment already exists."
fi

# ============================================================================
# Step 4: Install the installer package into the venv
# ============================================================================
echo "[INFO] Installing comfyui-installer..."
uv pip install -e "$SCRIPT_DIR" --python "$VENV_PY" --quiet

# ============================================================================
# Step 5: Launch the installer CLI
# ============================================================================
echo "[INFO] Starting installation..."
echo ""
"$VENV_PY" -m src.cli install --path "$INSTALL_PATH"

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
# Step 1.5: Ask for environment type (venv or conda)
# ============================================================================
INSTALL_TYPE="venv"
echo "What type of Python environment do you want to use?"
echo "  1: venv (Default, Recommended - isolated, fast)"
echo "  2: conda (Isolated local prefix via Miniconda)"
echo ""
read -rp "Choice (1 or 2, Enter for 1): " ENV_CHOICE

if [ "$ENV_CHOICE" = "2" ]; then
    INSTALL_TYPE="conda"
else
    INSTALL_TYPE="venv"
fi

echo ""
echo "[INFO] Environment type: $INSTALL_TYPE"
echo ""

# ============================================================================
# Step 1.6: Ask for custom nodes bundle
# ============================================================================
NODE_TIER="umeairt"
echo "Select custom nodes bundle:"
echo "  1: Minimal   - ComfyUI-Manager only"
echo "  2: UmeAiRT   - Manager + UmeAiRT Toolkit (Default, Recommended)"
echo "  3: Full      - All 34 nodes"
echo ""
read -rp "Choice (1, 2 or 3, Enter for 2): " NODE_CHOICE

case "$NODE_CHOICE" in
    1) NODE_TIER="minimal" ;;
    3) NODE_TIER="full" ;;
    *) NODE_TIER="umeairt" ;;
esac

echo ""
echo "[INFO] Nodes bundle: $NODE_TIER"
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
# Step 3: Create bootstrap venv (uv auto-downloads Python 3.11-3.13 if needed)
# ============================================================================
VENV_PATH="$INSTALL_PATH/scripts/venv"
VENV_PY="$VENV_PATH/bin/python"

if [ ! -f "$VENV_PY" ]; then
    echo "[INFO] Creating Python environment..."
    uv venv "$VENV_PATH" --python ">=3.11,<3.14" --seed --link-mode copy
    echo "[INFO] Python environment ready."
else
    echo "[INFO] Python environment already exists."
fi

# ============================================================================
# Step 4: Install the installer package into the venv
# ============================================================================
echo "[INFO] Installing umeairt-comfyui-installer..."
uv pip install -e "$SCRIPT_DIR" --python "$VENV_PY" --quiet

# ============================================================================
# Step 5: Launch the installer CLI
# ============================================================================
echo "[INFO] Starting installation..."
echo ""
"$VENV_PY" -m src.cli install --path "$INSTALL_PATH" --type "$INSTALL_TYPE" --nodes "$NODE_TIER"

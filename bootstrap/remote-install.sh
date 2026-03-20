#!/usr/bin/env bash
# ============================================================================
# UmeAiRT ComfyUI — Remote One-Liner Installer
#
# Usage:
#   curl -fsSL https://get.umeai.art/comfyui.sh | sh
#
# This script downloads the installer and delegates to Install.sh.
# ============================================================================

set -e

echo ""
echo "============================================================================"
echo "          UmeAiRT ComfyUI — Auto-Installer"
echo "============================================================================"
echo ""

# --- Check prerequisites ---
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "[ERROR] $1 is required but not found."
        echo "        $2"
        exit 1
    fi
}

check_cmd git "Install from: https://git-scm.com or your package manager"

# --- Download installer to temp ---
INSTALLER_DIR="${TMPDIR:-/tmp}/ComfyUI-Auto_installer"
REPO_URL="https://github.com/UmeAiRT/ComfyUI-Auto_installer.git"
BRANCH="python-rewrite"  # Change to 'main' after merge

if [ -d "$INSTALLER_DIR/.git" ]; then
    echo "[INFO] Updating installer..."
    git -C "$INSTALLER_DIR" pull --ff-only --quiet 2>/dev/null || {
        echo "[INFO] Pull failed, re-cloning..."
        rm -rf "$INSTALLER_DIR"
        git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALLER_DIR" --quiet
    }
else
    echo "[INFO] Downloading installer..."
    rm -rf "$INSTALLER_DIR"
    git clone --depth 1 -b "$BRANCH" "$REPO_URL" "$INSTALLER_DIR" --quiet
fi

echo "[INFO] Installer ready."
echo ""

# --- Launch Install.sh (it handles everything from here) ---
INSTALL_SH="$INSTALLER_DIR/Install.sh"
if [ ! -f "$INSTALL_SH" ]; then
    echo "[ERROR] Install.sh not found."
    exit 1
fi

chmod +x "$INSTALL_SH"
cd "$INSTALLER_DIR"
exec "$INSTALL_SH"

# ============================================================================
# UmeAiRT ComfyUI — Remote One-Liner Installer (PowerShell)
#
# Usage:
#   irm https://get.umeai.art/comfyui.ps1 | iex
#
# This script downloads the installer and delegates to Install.bat.
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "          UmeAiRT ComfyUI — Auto-Installer" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# --- Check prerequisites ---
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Git is required but not found in PATH." -ForegroundColor Red
    Write-Host "        Install from: https://git-scm.com/downloads/win" -ForegroundColor Yellow
    return
}

# --- Download installer to temp ---
$InstallerDir = Join-Path $env:TEMP "ComfyUI-Auto_installer"
$RepoUrl = "https://github.com/UmeAiRT/ComfyUI-Auto_installer.git"
$Branch = "python-rewrite"  # Change to 'main' after merge

if (Test-Path (Join-Path $InstallerDir ".git")) {
    Write-Host "[INFO] Updating installer..." -ForegroundColor Cyan
    git -C $InstallerDir pull --ff-only --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[INFO] Pull failed, re-cloning..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $InstallerDir
        git clone --depth 1 -b $Branch $RepoUrl $InstallerDir --quiet
    }
} else {
    Write-Host "[INFO] Downloading installer..." -ForegroundColor Cyan
    if (Test-Path $InstallerDir) { Remove-Item -Recurse -Force $InstallerDir }
    git clone --depth 1 -b $Branch $RepoUrl $InstallerDir --quiet
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to download installer. Check your internet connection." -ForegroundColor Red
    return
}

Write-Host "[INFO] Installer ready." -ForegroundColor Green
Write-Host ""

# --- Launch Install.bat (it handles everything from here) ---
$InstallBat = Join-Path $InstallerDir "Install.bat"
if (-not (Test-Path $InstallBat)) {
    Write-Host "[ERROR] Install.bat not found." -ForegroundColor Red
    return
}

Push-Location $InstallerDir
cmd /c "`"$InstallBat`""
Pop-Location

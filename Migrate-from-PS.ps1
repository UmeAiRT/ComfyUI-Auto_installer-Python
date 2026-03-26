# ============================================================================
# UmeAiRT ComfyUI — PowerShell to Python Migration Script
#
# Usage (one-liner):
#   irm https://get.umeai.art/migrate.ps1 | iex
#
# Usage (local):
#   powershell -ExecutionPolicy Bypass -File Migrate-from-PS.ps1
#
# This script migrates an existing PowerShell installation to the new
# Python installer. It preserves all user data (models, outputs, ComfyUI,
# custom nodes) and only replaces the installer infrastructure.
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "    UmeAiRT ComfyUI — Migration PowerShell -> Python" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# Step 1: Detect existing PowerShell installation
# ============================================================================

Write-Host "[Step 1/6] Detecting PowerShell installation..." -ForegroundColor Yellow

$InstallPath = ""

# Try current directory first
$markers = @(
    "scripts\custom_nodes.csv",
    "scripts\Install-ComfyUI-Phase1.ps1",
    "UmeAiRT-Install-ComfyUI.bat"
)

function Test-PSInstall {
    param([string]$Path)
    foreach ($m in $markers) {
        if (Test-Path (Join-Path $Path $m)) { return $true }
    }
    return $false
}

# Auto-detect: current dir, parent dir, common locations
$candidates = @(
    $PWD.Path,
    (Split-Path $PWD.Path -Parent),
    "$env:USERPROFILE\ComfyUI",
    "C:\ComfyUI",
    "D:\ComfyUI"
)

foreach ($c in $candidates) {
    if ($c -and (Test-Path $c) -and (Test-PSInstall $c)) {
        $InstallPath = $c
        break
    }
}

if (-not $InstallPath) {
    while ($true) {
        Write-Host ""
        Write-Host "[INFO] Could not auto-detect a PowerShell installation." -ForegroundColor Yellow
        Write-Host "       Enter the path to your existing ComfyUI installation"
        Write-Host "       (or type Q to quit):"
        $userInput = Read-Host "       Path"
        $userInput = $userInput.Trim('"').Trim("'")

        if ($userInput -eq "Q" -or $userInput -eq "q") {
            Write-Host "[INFO] Migration cancelled." -ForegroundColor Yellow
            exit 0
        }

        if (-not (Test-Path $userInput)) {
            Write-Host "[ERROR] Path does not exist: $userInput" -ForegroundColor Red
            continue
        }

        if (-not (Test-PSInstall $userInput)) {
            Write-Host "[ERROR] No PowerShell installation detected at: $userInput" -ForegroundColor Red
            Write-Host "        Expected files: scripts\custom_nodes.csv, scripts\Install-ComfyUI-Phase1.ps1, etc." -ForegroundColor DarkGray
            continue
        }

        $InstallPath = $userInput
        break
    }
}

Write-Host "[OK] Found installation at: $InstallPath" -ForegroundColor Green

# ============================================================================
# Step 2: Validate user data
# ============================================================================

Write-Host ""
Write-Host "[Step 2/6] Validating user data..." -ForegroundColor Yellow

$comfyPath = Join-Path $InstallPath "ComfyUI"
$modelsPath = Join-Path $InstallPath "models"
$outputPath = Join-Path $InstallPath "output"

$hasComfyUI = Test-Path $comfyPath
$hasModels  = Test-Path $modelsPath
$hasOutput  = Test-Path $outputPath

if ($hasComfyUI) { Write-Host "  ComfyUI/        : Found" -ForegroundColor Green }
else             { Write-Host "  ComfyUI/        : Not found (will be cloned)" -ForegroundColor Yellow }

if ($hasModels)  { Write-Host "  models/         : Found (PRESERVED)" -ForegroundColor Green }
else             { Write-Host "  models/         : Not found" -ForegroundColor DarkGray }

if ($hasOutput)  { Write-Host "  output/         : Found (PRESERVED)" -ForegroundColor Green }
else             { Write-Host "  output/         : Not found" -ForegroundColor DarkGray }

# Count custom nodes
$customNodesDir = Join-Path $comfyPath "custom_nodes"
$nodeCount = 0
if (Test-Path $customNodesDir) {
    $nodeCount = (Get-ChildItem -Directory $customNodesDir |
                  Where-Object { $_.Name -ne "__pycache__" -and -not $_.Name.StartsWith(".") }).Count
    Write-Host "  custom_nodes/   : $nodeCount nodes found (ALL PRESERVED)" -ForegroundColor Green
}

# ============================================================================
# Step 3: Confirm migration
# ============================================================================

Write-Host ""
Write-Host "============================================================================" -ForegroundColor White
Write-Host "  Migration Summary" -ForegroundColor White
Write-Host "============================================================================" -ForegroundColor White
Write-Host ""
Write-Host "  WILL BE PRESERVED:" -ForegroundColor Green
Write-Host "    - All models (checkpoints, LoRA, VAE, etc.)"
Write-Host "    - All generated outputs"
Write-Host "    - ComfyUI source code"
Write-Host "    - All custom nodes ($nodeCount nodes)"
Write-Host "    - ComfyUI user settings"
Write-Host ""
Write-Host "  WILL BE REMOVED:" -ForegroundColor Red
Write-Host "    - PowerShell scripts (scripts/*.ps1, *.psm1)"
Write-Host "    - Old Python environment (scripts/venv/ or Conda 'UmeAiRT')"
Write-Host "    - Old .bat launchers"
Write-Host "    - custom_nodes.csv, dependencies.json, snapshot.json"
Write-Host ""
Write-Host "  WILL BE CREATED:" -ForegroundColor Cyan
Write-Host "    - New Python environment (via uv)"
Write-Host "    - New launcher scripts"
Write-Host "    - Python dependencies for ALL custom nodes"
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Red
Write-Host "  WARNING: This operation is IRREVERSIBLE." -ForegroundColor Red
Write-Host "  The old PowerShell scripts and Python environment will be" -ForegroundColor Red
Write-Host "  permanently deleted. It is strongly recommended to back up" -ForegroundColor Red
Write-Host "  your entire installation folder before proceeding." -ForegroundColor Red
Write-Host "" -ForegroundColor Red
Write-Host "  Suggested backup command:" -ForegroundColor Yellow
Write-Host "    Copy-Item -Recurse `"$InstallPath`" `"${InstallPath}_backup`"" -ForegroundColor White
Write-Host "  ============================================================" -ForegroundColor Red
Write-Host ""

$confirm = ""
while ($confirm -notin @("Y", "N")) {
    $confirm = (Read-Host "  Proceed with migration? (Y/N)").ToUpper()
}
if ($confirm -ne "Y") {
    Write-Host "[INFO] Migration cancelled." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"; exit 0
}

# ============================================================================
# Step 4: Clean up PowerShell-specific files
# ============================================================================

Write-Host ""
Write-Host "[Step 3/6] Cleaning up PowerShell files..." -ForegroundColor Yellow

$scriptsDir = Join-Path $InstallPath "scripts"

# Remove old venv
$oldVenv = Join-Path $scriptsDir "venv"
if (Test-Path $oldVenv) {
    Write-Host "  Removing old Python venv..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $oldVenv -ErrorAction SilentlyContinue
}

# Remove Conda environment if present
if (Get-Command conda -ErrorAction SilentlyContinue) {
    Write-Host "  Removing Conda 'UmeAiRT' environment..." -ForegroundColor DarkGray
    conda env remove -n UmeAiRT -y 2>$null
}

# Remove PS scripts and configs
$psFiles = @(
    "scripts\Install-ComfyUI-Phase1.ps1",
    "scripts\Install-ComfyUI-Phase2.ps1",
    "scripts\Update-ComfyUI.ps1",
    "scripts\Bootstrap-Downloader.ps1",
    "scripts\Launch-Phase2.ps1",
    "scripts\UmeAiRTUtils.psm1",
    "scripts\Download-FLUX-Models.ps1",
    "scripts\Download-HIDREAM-Models.ps1",
    "scripts\Download-LTX1-Models.ps1",
    "scripts\Download-LTX2-Models.ps1",
    "scripts\Download-QWEN-Models.ps1",
    "scripts\Download-WAN2.1-Models.ps1",
    "scripts\Download-WAN2.2-Models.ps1",
    "scripts\Download-Z-IMAGES-Models.ps1",
    "scripts\custom_nodes.csv",
    "scripts\snapshot.json",
    "scripts\environment.yml",
    "scripts\comfy.settings.json",
    "scripts\comfyui_triton_sageattention.py",
    "scripts\install_type"
)

foreach ($f in $psFiles) {
    $fullPath = Join-Path $InstallPath $f
    if (Test-Path $fullPath) {
        Remove-Item -Force $fullPath -ErrorAction SilentlyContinue
        Write-Host "  Removed: $f" -ForegroundColor DarkGray
    }
}

# Remove old .bat launchers (PS versions)
$oldBats = @(
    "UmeAiRT-Install-ComfyUI.bat",
    "UmeAiRT-Start-ComfyUI.bat",
    "UmeAiRT-Start-ComfyUI_LowVRAM.bat",
    "UmeAiRT-Update-ComfyUI.bat",
    "UmeAiRT-Download_models.bat"
)

foreach ($b in $oldBats) {
    $fullPath = Join-Path $InstallPath $b
    if (Test-Path $fullPath) {
        Remove-Item -Force $fullPath -ErrorAction SilentlyContinue
        Write-Host "  Removed: $b" -ForegroundColor DarkGray
    }
}

Write-Host "[OK] PowerShell files cleaned." -ForegroundColor Green

# ============================================================================
# Step 5: Download Python installer
# ============================================================================

Write-Host ""
Write-Host "[Step 4/6] Downloading Python installer..." -ForegroundColor Yellow

$InstallerDir = Join-Path $env:TEMP "ComfyUI-Auto_installer"
$RepoUrl      = "https://github.com/UmeAiRT/ComfyUI-Auto_installer-Python.git"
$Branch        = "main"
$HF_ZIP       = "https://huggingface.co/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/main/releases/ComfyUI-Auto_installer-latest.zip"
$MS_ZIP       = "https://www.modelscope.ai/datasets/UmeAiRT/ComfyUI-Auto-Installer-Assets/resolve/master/releases/ComfyUI-Auto_installer-latest.zip"

$downloaded = $false

# Source 1: Git
if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path (Join-Path $InstallerDir ".git")) {
        Write-Host "  Updating installer (Git)..." -ForegroundColor Cyan
        git -C $InstallerDir pull --ff-only --quiet 2>$null
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -Recurse -Force $InstallerDir
            git clone --depth 1 -b $Branch $RepoUrl $InstallerDir --quiet
        }
    } else {
        Write-Host "  Downloading installer (Git)..." -ForegroundColor Cyan
        if (Test-Path $InstallerDir) { Remove-Item -Recurse -Force $InstallerDir }
        git clone --depth 1 -b $Branch $RepoUrl $InstallerDir --quiet
    }
    if ($LASTEXITCODE -eq 0) { $downloaded = $true }
}

# Source 2: HuggingFace ZIP
if (-not $downloaded) {
    Write-Host "  Git unavailable. Trying HuggingFace..." -ForegroundColor Yellow
    try {
        $zipPath = Join-Path $env:TEMP "ComfyUI-Auto_installer.zip"
        if (Test-Path $InstallerDir) { Remove-Item -Recurse -Force $InstallerDir }
        Invoke-WebRequest -Uri $HF_ZIP -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
        Remove-Item $zipPath -Force
        $downloaded = $true
    } catch {
        Write-Host "  HuggingFace failed." -ForegroundColor Yellow
    }
}

# Source 3: ModelScope ZIP
if (-not $downloaded) {
    Write-Host "  Trying ModelScope..." -ForegroundColor Yellow
    try {
        $zipPath = Join-Path $env:TEMP "ComfyUI-Auto_installer.zip"
        if (Test-Path $InstallerDir) { Remove-Item -Recurse -Force $InstallerDir }
        Invoke-WebRequest -Uri $MS_ZIP -OutFile $zipPath -UseBasicParsing
        Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
        Remove-Item $zipPath -Force
        $downloaded = $true
    } catch {
        Write-Host "[ERROR] All download sources failed." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
}

# Verify
$PyProject = Join-Path $InstallerDir "pyproject.toml"
if (-not (Test-Path $PyProject)) {
    Write-Host "[ERROR] Downloaded installer appears corrupted." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

Write-Host "[OK] Installer downloaded." -ForegroundColor Green

# ============================================================================
# Step 5: Bootstrap uv + venv + install CLI
# ============================================================================

Write-Host ""
Write-Host "[Step 5/6] Setting up Python environment..." -ForegroundColor Yellow

$uvDir = Join-Path $InstallPath "scripts\uv"
$uvExe = Join-Path $uvDir "uv.exe"

if (-not (Test-Path $uvExe)) {
    Write-Host "  Downloading uv package manager..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $uvDir -Force | Out-Null
    $uvZip = Join-Path $env:TEMP "uv-installer.zip"
    curl.exe -LsSf -o $uvZip "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to download uv." -ForegroundColor Red
        Read-Host "Press Enter to exit"; exit 1
    }
    tar -xf $uvZip -C $uvDir
    Remove-Item $uvZip -ErrorAction SilentlyContinue
    Write-Host "  uv installed." -ForegroundColor Green
} else {
    Write-Host "  uv already available." -ForegroundColor Green
}

# Create venv
$venvPath = Join-Path $InstallPath "scripts\venv"
$venvPy = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "  Creating Python environment..." -ForegroundColor Cyan
    & $uvExe venv $venvPath --python ">=3.11,<3.14" --python-preference only-system --seed --link-mode copy 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  No compatible system Python found, downloading..." -ForegroundColor Yellow
        & $uvExe venv $venvPath --python ">=3.11,<3.14" --seed --link-mode copy
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to create Python environment." -ForegroundColor Red
            Read-Host "Press Enter to exit"; exit 1
        }
    }
    Write-Host "  Python environment ready." -ForegroundColor Green
} else {
    Write-Host "  Python environment already exists." -ForegroundColor Green
}

# Install the installer CLI
Write-Host "  Installing umeairt-comfyui-installer..." -ForegroundColor Cyan
& $uvExe pip install -e $InstallerDir --python $venvPy --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install installer CLI." -ForegroundColor Red
    Read-Host "Press Enter to exit"; exit 1
}

Write-Host "[OK] Python environment ready." -ForegroundColor Green

# ============================================================================
# Step 6: Run the installer (reuses existing ComfyUI + nodes)
# ============================================================================

Write-Host ""
Write-Host "[Step 6/6] Running Python installer (reusing existing data)..." -ForegroundColor Yellow
Write-Host ""

& $venvPy -m src.cli install --path $InstallPath --type venv --nodes full

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "    Migration Complete!" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Your installation has been migrated to the Python version." -ForegroundColor White
Write-Host "  All models, outputs, and custom nodes have been preserved." -ForegroundColor White
Write-Host ""
Write-Host "  New launcher scripts:" -ForegroundColor Cyan
Write-Host "    - UmeAiRT-Start-ComfyUI.bat      (launch ComfyUI)"
Write-Host "    - UmeAiRT-Start-ComfyUI_LowVRAM.bat (low VRAM mode)"
Write-Host "    - UmeAiRT-Manager.bat             (TUI manager)"
Write-Host ""

Read-Host "Press Enter to close"

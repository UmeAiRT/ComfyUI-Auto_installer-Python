"""
Configuration system with Pydantic validation.

Replaces the scattered configuration across dependencies.json, repo-config.json,
and hardcoded values in PowerShell scripts. Provides a single, typed, validated
configuration model.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class ToolConfig(BaseModel):
    """Configuration for an external tool (e.g. VS Build Tools)."""

    install_path: str = ""
    url: str = ""
    arguments: str = ""
    sha256: str = ""


class ToolsConfig(BaseModel):
    """All external tools configuration."""

    vs_build_tools: ToolConfig = Field(default_factory=ToolConfig)
    git_windows: ToolConfig = Field(default_factory=lambda: ToolConfig(
        url="https://huggingface.co/UmeAiRT/ComfyUI-Auto_installer/resolve/main/bin/Git-2.53.0.2-64-bit.exe",
        sha256="194362cf24cd0db4b573096108460a34c7f80a20c5f2aa60d06ef817be9f73a1",
    ))
    aria2_windows: ToolConfig = Field(default_factory=lambda: ToolConfig(
        url="https://huggingface.co/UmeAiRT/ComfyUI-Auto_installer/resolve/main/bin/aria2-1.37.0-win-64bit-build1.zip",
        sha256="67d015301eef0b612191212d564c5bb0a14b5b9c4796b76454276a4d28d9b288",
    ))
    miniconda_windows: ToolConfig = Field(default_factory=lambda: ToolConfig(
        url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe",
        sha256="c76f35d66f8a19a3b33786abb86dacf0bf8d892a55d9dde38eccb0da0820ae99",
    ))


class TorchConfig(BaseModel):
    """PyTorch installation configuration."""

    packages: str = "torch torchvision torchaudio xformers"
    index_url: str = "https://download.pytorch.org/whl/cu130"


class WheelConfig(BaseModel):
    """A pre-built wheel package to install.

    Supports version-aware wheels via the ``versions`` mapping:
    each key is a CPython tag (e.g. ``"cp311"``, ``"cp312"``)
    and the value is the download URL for that version.

    Optionally, ``checksums`` maps CPython tags to expected
    SHA-256 hex digests for supply-chain verification.

    Legacy format (flat ``name`` + ``url``) is still supported.
    """

    name: str = ""
    url: str = ""
    versions: dict[str, str] = Field(default_factory=dict)
    checksums: dict[str, str] = Field(default_factory=dict)

    def resolve(
        self,
        python_version: tuple[int, int],
        cuda_tag: str = "",
    ) -> tuple[str, str, str | None] | None:
        """Pick the wheel matching the running Python and CUDA version.

        Resolution order for versioned wheels:
        1. ``{cuda_tag}_{cpython_tag}`` — exact CUDA + Python match
        2. ``{cpython_tag}`` — CUDA-agnostic fallback

        Args:
            python_version: (major, minor) tuple, e.g. (3, 13).
            cuda_tag: CUDA tag, e.g. ``"cu130"`` or ``"cu128"``.

        Returns:
            (name, url, sha256_or_None) tuple, or None if no match.
        """
        cp_tag = f"cp{python_version[0]}{python_version[1]}"

        if self.versions:
            # Try CUDA-specific key first, then cpython-only fallback
            for key in ([f"{cuda_tag}_{cp_tag}", cp_tag] if cuda_tag else [cp_tag]):
                url = self.versions.get(key)
                if url:
                    whl_name = url.rsplit("/", 1)[-1].removesuffix(".whl")
                    checksum = self.checksums.get(key)
                    return whl_name, url, checksum
            return None

        # Legacy: flat name + url (assumed to match current Python)
        if self.name and self.url:
            return self.name, self.url, None
        return None


class PipPackages(BaseModel):
    """All pip package configurations."""

    upgrade: list[str] = Field(default_factory=lambda: ["pip", "wheel"])
    torch: dict[str, TorchConfig] | TorchConfig = Field(
        default_factory=lambda: {
            "cu130": TorchConfig(
                packages="torch==2.10.0+cu130 torchvision torchaudio xformers",
                index_url="https://download.pytorch.org/whl/cu130",
            ),
            "cu128": TorchConfig(
                packages="torch==2.10.0+cu128 torchvision torchaudio xformers",
                index_url="https://download.pytorch.org/whl/cu128",
            ),
        }
    )
    comfyui_requirements: str = "requirements.txt"
    wheels: list[WheelConfig] = Field(default_factory=list)
    standard: list[str] = Field(default_factory=list)
    git_repos: list[str] = Field(default_factory=list)

    def get_torch(self, cuda_tag: str) -> TorchConfig | None:
        """Get the TorchConfig for a specific CUDA tag.

        Handles both legacy (single TorchConfig) and multi-CUDA (dict) formats.

        Args:
            cuda_tag: CUDA tag, e.g. ``"cu130"`` or ``"cu128"``.

        Returns:
            Matching TorchConfig, or ``None`` if not available.
        """
        if isinstance(self.torch, dict):
            return self.torch.get(cuda_tag)
        # Legacy single TorchConfig — return it for any tag
        return self.torch

    @property
    def supported_cuda_tags(self) -> list[str]:
        """List supported CUDA tags from the torch configuration."""
        if isinstance(self.torch, dict):
            return list(self.torch.keys())
        return []


class RepositoryConfig(BaseModel):
    """A git repository source."""

    url: str


class RepositoriesConfig(BaseModel):
    """All git repositories."""

    comfyui: RepositoryConfig = Field(
        default_factory=lambda: RepositoryConfig(url="https://github.com/comfyanonymous/ComfyUI.git")
    )
    workflows: RepositoryConfig = Field(
        default_factory=lambda: RepositoryConfig(url="https://github.com/UmeAiRT/ComfyUI-Workflows")
    )


class FileEntry(BaseModel):
    """A file to download with its destination."""

    url: str
    destination: str


class FilesConfig(BaseModel):
    """All downloadable files."""

    comfy_settings: FileEntry | None = None


class TritonConfig(BaseModel):
    """Triton installation configuration."""

    windows_package: str = "triton-windows"
    linux_package: str = "triton"
    version_constraints: dict[str, str] = Field(default_factory=dict)


class SageAttentionConfig(BaseModel):
    """SageAttention installation configuration."""

    pypi_package: str = "sageattention"


class OptimizationsConfig(BaseModel):
    """GPU optimization packages configuration."""

    triton: TritonConfig = Field(default_factory=TritonConfig)
    sageattention: SageAttentionConfig = Field(default_factory=SageAttentionConfig)


class DependenciesConfig(BaseModel):
    """
    Complete dependencies configuration.

    Typed replacement for dependencies.json.
    """

    repositories: RepositoriesConfig = Field(default_factory=RepositoriesConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    pip_packages: PipPackages = Field(default_factory=PipPackages)
    files: FilesConfig = Field(default_factory=FilesConfig)
    optimizations: OptimizationsConfig | None = None


class InstallerSettings(BaseModel):
    """
    User-local installer settings.

    Replaces repo-config.json and hardcoded values.
    This file should NEVER be overwritten by bootstrap/update.
    """

    # Network
    listen_address: str = "127.0.0.1"  # Fixed! Was 0.0.0.0 in PowerShell version
    listen_port: int = 8188

    # GitHub source (for forks)
    gh_user: str = "UmeAiRT"
    gh_reponame: str = "ComfyUI-Auto_installer"
    gh_branch: str = "main"

    # Installation
    install_path: Path = Field(default_factory=lambda: Path.cwd())
    install_type: str = "venv"  # "venv" or "conda"
    package_manager: str = "uv"  # "uv" or "pip"

    # Launch options
    use_sage_attention: bool = True
    auto_launch: bool = True


def load_dependencies(path: Path) -> DependenciesConfig:
    """
    Load and validate dependencies.json.

    Args:
        path: Path to dependencies.json file.

    Returns:
        Validated DependenciesConfig object.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the JSON is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Dependencies file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return DependenciesConfig.model_validate(data)


def load_settings(path: Path) -> InstallerSettings:
    """
    Load user-local settings from local-config.json.

    If the file doesn't exist, returns defaults.

    Args:
        path: Path to local-config.json.

    Returns:
        InstallerSettings with loaded or default values.
    """
    if not path.exists():
        return InstallerSettings()

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return InstallerSettings.model_validate(data)


def save_settings(settings: InstallerSettings, path: Path) -> None:
    """
    Save settings to local-config.json.

    Args:
        settings: The settings to save.
        path: Destination file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            settings.model_dump(mode="json"),
            f,
            indent=2,
            default=str,
        )

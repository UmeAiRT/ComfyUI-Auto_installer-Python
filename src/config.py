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


class ToolsConfig(BaseModel):
    """All external tools configuration."""

    vs_build_tools: ToolConfig = Field(default_factory=ToolConfig)


class TorchConfig(BaseModel):
    """PyTorch installation configuration."""

    packages: str = "torch torchvision torchaudio xformers"
    index_url: str = "https://download.pytorch.org/whl/cu130"


class WheelConfig(BaseModel):
    """A pre-built wheel package to install."""

    name: str
    url: str


class PipPackages(BaseModel):
    """All pip package configurations."""

    upgrade: list[str] = Field(default_factory=lambda: ["pip", "wheel"])
    torch: TorchConfig = Field(default_factory=TorchConfig)
    comfyui_requirements: str = "requirements.txt"
    wheels: list[WheelConfig] = Field(default_factory=list)
    standard: list[str] = Field(default_factory=list)
    git_repos: list[str] = Field(default_factory=list)


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


class DependenciesConfig(BaseModel):
    """
    Complete dependencies configuration.

    Typed replacement for dependencies.json.
    """

    repositories: RepositoriesConfig = Field(default_factory=RepositoriesConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    pip_packages: PipPackages = Field(default_factory=PipPackages)
    files: FilesConfig = Field(default_factory=FilesConfig)


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

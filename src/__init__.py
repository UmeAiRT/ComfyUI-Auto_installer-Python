"""ComfyUI Auto-Installer — Cross-platform automated installer for ComfyUI."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("umeairt-comfyui-installer")
except PackageNotFoundError:
    __version__ = "5.0.0.dev0"  # fallback for running from source without install


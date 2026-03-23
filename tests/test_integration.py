"""Integration test: verify the full installer chain works end-to-end."""

import sys
from pathlib import Path


def test_dependencies_parsing():
    """The real dependencies.json should parse with our Pydantic models."""
    from src.config import load_dependencies

    deps = load_dependencies(Path("scripts/dependencies.json"))
    assert deps.repositories.comfyui.url.startswith("https://")
    assert "torch" in deps.pip_packages.get_torch("cu130").packages  # type: ignore
    assert len(deps.pip_packages.wheels) >= 1
    assert len(deps.pip_packages.standard) >= 5


def test_platform_detection():
    """Platform factory should return the correct platform for the current OS."""
    from src.platform.base import get_platform

    p = get_platform()
    if sys.platform == "win32":
        assert p.__class__.__name__ == "WindowsPlatform"
    elif sys.platform == "darwin":
        assert p.__class__.__name__ == "MacOSPlatform"
    else:
        assert p.__class__.__name__ == "LinuxPlatform"


def test_python_detection():
    """Should detect our current Python."""
    from src.platform.base import get_platform

    p = get_platform()
    # We're running Python 3.14, so looking for 3.13 may fail,
    # but the method should return None gracefully (not crash)
    major_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    result = p.detect_python(major_minor)
    assert result is not None, f"Could not detect Python {major_minor}"
    assert result.exists()


def test_git_available():
    """Git should be detected."""
    from src.utils.commands import check_command_exists, get_command_version

    assert check_command_exists("git")
    ver = get_command_version("git")
    assert ver is not None
    assert "git version" in ver


def test_installer_modules_import():
    """All installer modules should import without errors."""


def test_check_prerequisites():
    """check_prerequisites should run without crashing."""
    from src.installer.system import check_prerequisites
    from src.utils.logging import setup_logger

    log = setup_logger(total_steps=1)
    result = check_prerequisites(log)
    assert isinstance(result, bool)


def test_dependencies_parsing_optimizations():
    """The optimizations section in dependencies.json should parse correctly."""
    from src.config import load_dependencies

    deps = load_dependencies(Path("scripts/dependencies.json"))
    assert deps.optimizations is not None
    assert len(deps.optimizations.packages) >= 3

    # Find packages by name
    pkg_names = {p.name for p in deps.optimizations.packages}
    assert "triton" in pkg_names
    assert "sageattention" in pkg_names
    assert "flash-attn" in pkg_names

    # Validate triton has platform-specific packages and torch constraints
    triton = next(p for p in deps.optimizations.packages if p.name == "triton")
    assert triton.get_package_name("windows") == "triton-windows"
    assert triton.get_package_name("linux") == "triton"
    assert "2.10" in triton.torch_constraints

    # Validate flash-attn requires nvidia + linux
    flash = next(p for p in deps.optimizations.packages if p.name == "flash-attn")
    assert "nvidia" in flash.requires
    assert "linux" in flash.requires


def test_launcher_has_listen_address(tmp_path):
    """Launchers should read listen address from config and use LISTEN_ADDR variable."""
    from src.installer.finalize import create_launchers
    from src.utils.logging import setup_logger

    log = setup_logger(total_steps=1)

    # Create required template directory
    templates_dir = Path(__file__).resolve().parent.parent / "src" / "installer" / "templates"
    assert templates_dir.exists(), f"Templates not found at {templates_dir}"

    create_launchers(tmp_path, log)

    # Check bat or sh depending on platform
    if sys.platform == "win32":
        launcher = tmp_path / "UmeAiRT-Start-ComfyUI.bat"
    else:
        launcher = tmp_path / "UmeAiRT-Start-ComfyUI.sh"

    assert launcher.exists(), f"Launcher not created: {launcher}"
    content = launcher.read_text(encoding="utf-8")

    # Should have listen address config reading (not interactive prompt)
    assert "LISTEN_ADDR" in content, "LISTEN_ADDR variable should be used"
    assert "listen_address" in content, "Should read from listen_address config file"

    # --listen should use the variable, not a hardcoded value
    assert "--listen %LISTEN_ADDR%" in content or '--listen "$LISTEN_ADDR"' in content, \
        "--listen should use the LISTEN_ADDR variable, not a hardcoded value"


def test_launcher_no_hardcoded_listen(tmp_path):
    """The --listen flag should NOT be in the hardcoded {args} — only in the template."""
    from src.installer.finalize import create_launchers
    from src.utils.logging import setup_logger

    log = setup_logger(total_steps=1)
    create_launchers(tmp_path, log)

    if sys.platform == "win32":
        launcher = tmp_path / "UmeAiRT-Start-ComfyUI.bat"
    else:
        launcher = tmp_path / "UmeAiRT-Start-ComfyUI.sh"

    content = launcher.read_text(encoding="utf-8")

    # The args string should not contain a bare "--listen 127.0.0.1" or "--listen 0.0.0.0"
    # It should only appear via %LISTEN_ADDR% / $LISTEN_ADDR
    assert "--listen 127.0.0.1 --auto" not in content, \
        "listen address should not be hardcoded in args"
    assert "--listen 0.0.0.0 --auto" not in content, \
        "listen address should not be hardcoded in args"


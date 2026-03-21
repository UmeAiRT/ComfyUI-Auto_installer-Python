"""Tests for the dependency installation module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.installer.dependencies import (
    install_core_dependencies,
    install_custom_nodes,
    install_python_packages,
    install_wheels,
)


class TestInstallCoreDependencies:
    """Tests for install_core_dependencies."""

    def test_installs_torch_and_requirements(self, tmp_path: Path) -> None:
        """Should call uv_install for torch and ComfyUI requirements."""
        log = MagicMock()
        python_exe = tmp_path / "python"
        comfy_path = tmp_path / "ComfyUI"
        comfy_path.mkdir()

        # Create requirements file
        req_file = comfy_path / "requirements.txt"
        req_file.write_text("torch\n")

        deps = MagicMock()
        deps.pip_packages.torch.packages = "torch torchvision"
        deps.pip_packages.torch.index_url = "https://example.com/whl/cu130"
        deps.pip_packages.comfyui_requirements = "requirements.txt"

        with patch("src.installer.dependencies.uv_install") as mock_uv:
            install_core_dependencies(python_exe, comfy_path, deps, log)

            assert mock_uv.call_count == 2
            # First call: torch
            first_call = mock_uv.call_args_list[0]
            assert first_call[0] == (python_exe, ["torch", "torchvision"])
            assert first_call[1]["index_url"] == "https://example.com/whl/cu130"

    def test_skips_requirements_if_missing(self, tmp_path: Path) -> None:
        """Should only install torch if requirements.txt doesn't exist."""
        log = MagicMock()
        python_exe = tmp_path / "python"
        comfy_path = tmp_path / "ComfyUI"
        comfy_path.mkdir()

        deps = MagicMock()
        deps.pip_packages.torch.packages = "torch"
        deps.pip_packages.torch.index_url = "https://example.com"
        deps.pip_packages.comfyui_requirements = "requirements.txt"

        with patch("src.installer.dependencies.uv_install") as mock_uv:
            install_core_dependencies(python_exe, comfy_path, deps, log)
            assert mock_uv.call_count == 1


class TestInstallPythonPackages:
    """Tests for install_python_packages."""

    def test_installs_standard_packages(self, tmp_path: Path) -> None:
        """Should call uv_install with the standard packages list."""
        log = MagicMock()
        python_exe = tmp_path / "python"

        deps = MagicMock()
        deps.pip_packages.standard = ["numpy", "pillow", "scipy"]

        with patch("src.installer.dependencies.uv_install") as mock_uv:
            install_python_packages(python_exe, deps, log)
            mock_uv.assert_called_once_with(python_exe, ["numpy", "pillow", "scipy"])

    def test_skips_if_no_standard_packages(self, tmp_path: Path) -> None:
        """Should not call uv_install if standard list is empty."""
        log = MagicMock()
        python_exe = tmp_path / "python"

        deps = MagicMock()
        deps.pip_packages.standard = []

        with patch("src.installer.dependencies.uv_install") as mock_uv:
            install_python_packages(python_exe, deps, log)
            mock_uv.assert_not_called()


class TestInstallWheels:
    """Tests for install_wheels."""

    def test_downloads_and_installs_wheels(self, tmp_path: Path) -> None:
        """Should download, install, and clean up each wheel."""
        log = MagicMock()
        python_exe = tmp_path / "python"
        install_path = tmp_path / "install"
        scripts_dir = install_path / "scripts"
        scripts_dir.mkdir(parents=True)

        wheel_mock = MagicMock()
        wheel_mock.name = "test-package"
        wheel_mock.resolve.return_value = ("test_pkg-1.0-cp313", "https://example.com/test.whl", None)

        deps = MagicMock()
        deps.pip_packages.wheels = [wheel_mock]

        with (
            patch("src.utils.python_info.detect_venv_python_version", return_value=(3, 13)),
            patch("src.installer.dependencies.download_file") as mock_dl,
            patch("src.installer.dependencies.uv_install") as mock_uv,
        ):
            install_wheels(python_exe, install_path, deps, log)

            mock_dl.assert_called_once()
            mock_uv.assert_called_once()

    def test_skips_if_no_wheels(self, tmp_path: Path) -> None:
        """Should return early if wheels list is empty."""
        log = MagicMock()
        deps = MagicMock()
        deps.pip_packages.wheels = []

        with patch("src.installer.dependencies.uv_install") as mock_uv:
            install_wheels(tmp_path / "python", tmp_path, deps, log)
            mock_uv.assert_not_called()

    def test_handles_wheel_not_available(self, tmp_path: Path) -> None:
        """Should skip wheel if resolve() returns None."""
        log = MagicMock()
        python_exe = tmp_path / "python"
        install_path = tmp_path / "install"
        scripts_dir = install_path / "scripts"
        scripts_dir.mkdir(parents=True)

        wheel_mock = MagicMock()
        wheel_mock.name = "unavailable-pkg"
        wheel_mock.resolve.return_value = None

        deps = MagicMock()
        deps.pip_packages.wheels = [wheel_mock]

        with (
            patch("src.utils.python_info.detect_venv_python_version", return_value=(3, 13)),
            patch("src.installer.dependencies.download_file") as mock_dl,
        ):
            install_wheels(python_exe, install_path, deps, log)
            mock_dl.assert_not_called()
            log.warning.assert_called_once()

    def test_handles_download_failure(self, tmp_path: Path) -> None:
        """Should log warning and continue if download fails."""
        log = MagicMock()
        python_exe = tmp_path / "python"
        install_path = tmp_path / "install"
        scripts_dir = install_path / "scripts"
        scripts_dir.mkdir(parents=True)

        wheel_mock = MagicMock()
        wheel_mock.name = "fail-pkg"
        wheel_mock.resolve.return_value = ("fail-1.0", "https://example.com/fail.whl", None)

        deps = MagicMock()
        deps.pip_packages.wheels = [wheel_mock]

        with (
            patch("src.utils.python_info.detect_venv_python_version", return_value=(3, 12)),
            patch(
                "src.installer.dependencies.download_file",
                side_effect=Exception("network error"),
            ),
        ):
            install_wheels(python_exe, install_path, deps, log)
            log.warning.assert_called_once()


class TestInstallCustomNodes:
    """Tests for install_custom_nodes."""

    def test_skips_if_manifest_not_found(self, tmp_path: Path) -> None:
        """Should warn and return if custom_nodes.json is missing."""
        log = MagicMock()
        comfy_path = tmp_path / "ComfyUI"
        comfy_path.mkdir()
        install_path = tmp_path / "install"
        install_path.mkdir()
        (install_path / "scripts").mkdir()

        with patch(
            "src.installer.environment.find_source_scripts",
            side_effect=FileNotFoundError,
        ):
            install_custom_nodes(
                tmp_path / "python", comfy_path, install_path, log, node_tier="full"
            )
            log.warning.assert_called_once()

    def test_loads_and_installs_nodes(self, tmp_path: Path) -> None:
        """Should load manifest, filter by tier, and install nodes."""
        import json

        log = MagicMock()
        comfy_path = tmp_path / "ComfyUI"
        custom_nodes_dir = comfy_path / "custom_nodes"
        custom_nodes_dir.mkdir(parents=True)
        install_path = tmp_path / "install"
        scripts_dir = install_path / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create a minimal manifest
        manifest_data = {"nodes": []}
        (scripts_dir / "custom_nodes.json").write_text(json.dumps(manifest_data))

        with (
            patch("src.installer.nodes.load_manifest") as mock_load,
            patch("src.installer.nodes.filter_by_tier") as mock_filter,
            patch("src.installer.nodes.install_all_nodes") as mock_install,
        ):
            mock_load.return_value = ["node1", "node2"]
            mock_filter.return_value = ["node1"]

            install_custom_nodes(
                tmp_path / "python", comfy_path, install_path, log, node_tier="minimal"
            )

            mock_load.assert_called_once()
            mock_filter.assert_called_once_with(["node1", "node2"], "minimal")
            mock_install.assert_called_once()

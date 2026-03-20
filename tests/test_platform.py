"""Tests for the platform abstraction layer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.platform.base import Platform, get_platform


class TestGetPlatform:
    """Tests for the get_platform factory."""

    def test_returns_platform_instance(self) -> None:
        """Should return a Platform subclass for the current OS."""
        platform = get_platform()
        assert isinstance(platform, Platform)

    def test_windows_returns_windows_platform(self) -> None:
        """On win32, should return WindowsPlatform."""
        with patch("src.platform.base.sys") as mock_sys:
            mock_sys.platform = "win32"
            platform = get_platform()
            assert platform.name == "windows"

    def test_linux_returns_linux_platform(self) -> None:
        """On linux, should return LinuxPlatform."""
        with patch("src.platform.base.sys") as mock_sys:
            mock_sys.platform = "linux"
            platform = get_platform()
            assert platform.name == "linux"

    def test_unsupported_raises(self) -> None:
        """Should raise NotImplementedError for unknown platforms."""
        with (
            patch("src.platform.base.sys") as mock_sys,
            pytest.raises(NotImplementedError, match="not supported"),
        ):
            mock_sys.platform = "aix"
            get_platform()


class TestIsLink:
    """Tests for the base is_link method."""

    def test_regular_dir_is_not_link(self, tmp_path: Path) -> None:
        """A regular directory should not be detected as a link."""
        d = tmp_path / "regular"
        d.mkdir()
        platform = get_platform()
        assert platform.is_link(d) is False

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        """A path that doesn't exist should not be a link."""
        platform = get_platform()
        assert platform.is_link(tmp_path / "no_exist") is False


class TestPlatformProperties:
    """Tests for platform properties."""

    def test_name_is_string(self) -> None:
        """Platform name should be a non-empty string."""
        platform = get_platform()
        assert isinstance(platform.name, str)
        assert len(platform.name) > 0

    def test_detect_python_returns_path_or_none(self) -> None:
        """detect_python should return Path or None."""
        platform = get_platform()
        result = platform.detect_python("3.13")
        assert result is None or isinstance(result, Path)


class TestWindowsPlatform:
    """Tests for WindowsPlatform (mocked for cross-platform CI)."""

    def _make_platform(self):
        """Create a WindowsPlatform instance."""
        from src.platform.windows import WindowsPlatform
        return WindowsPlatform()

    def test_name_is_windows(self) -> None:
        wp = self._make_platform()
        assert wp.name == "windows"

    def test_create_link_already_junction(self, tmp_path: Path) -> None:
        """Should skip if source is already a junction/link."""
        wp = self._make_platform()
        source = tmp_path / "link"
        source.mkdir()

        with (
            patch.object(wp, "is_link", return_value=True),
            patch("src.platform.windows.get_logger") as mock_get,
        ):
            mock_get.return_value = MagicMock()
            wp.create_link(source, tmp_path / "target")
            # Should not raise, should log info

    def test_create_link_already_exists_not_junction(self, tmp_path: Path) -> None:
        """Should raise RuntimeError if source exists but is not a junction."""
        wp = self._make_platform()
        source = tmp_path / "link"
        source.mkdir()

        with (
            patch.object(wp, "is_link", return_value=False),
            patch("src.platform.windows.get_logger") as mock_get,
            pytest.raises(RuntimeError, match="Cannot create junction"),
        ):
            mock_get.return_value = MagicMock()
            wp.create_link(source, tmp_path / "target")

    def test_create_link_success(self, tmp_path: Path) -> None:
        """Should call mklink and report success when subprocess returns 0."""
        wp = self._make_platform()
        source = tmp_path / "new_link"
        target = tmp_path / "target"
        target.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0

        # source doesn't exist initially, subprocess.run succeeds,
        # then we need source.exists() to return True for the verification check.
        original_exists = Path.exists

        def patched_exists(self_path):
            # After mklink "runs", treat source as existing
            if self_path == source:
                return patched_exists._post_mklink
            return original_exists(self_path)

        patched_exists._post_mklink = False

        def fake_run(*args, **kwargs):
            patched_exists._post_mklink = True
            return mock_result

        with (
            patch("src.platform.windows.get_logger") as mock_get,
            patch("src.platform.windows.subprocess.run", side_effect=fake_run),
            patch.object(Path, "exists", patched_exists),
        ):
            mock_get.return_value = MagicMock()
            wp.create_link(source, target)

    def test_is_admin_returns_bool(self) -> None:
        """is_admin should return a boolean."""
        wp = self._make_platform()
        result = wp.is_admin()
        assert isinstance(result, bool)

    def test_get_app_data_dir_returns_path(self) -> None:
        """get_app_data_dir should return a Path."""
        wp = self._make_platform()
        result = wp.get_app_data_dir()
        assert isinstance(result, Path)

    def test_detect_python_returns_path_or_none(self) -> None:
        """detect_python should return Path or None."""
        wp = self._make_platform()
        with (
            patch("src.platform.windows.get_logger") as mock_get,
            patch("src.platform.windows.shutil.which", return_value=None),
        ):
            mock_get.return_value = MagicMock()
            result = wp.detect_python("3.99")
            assert result is None

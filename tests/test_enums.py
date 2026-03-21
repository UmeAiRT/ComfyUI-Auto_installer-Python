"""Tests for the enums module."""

from __future__ import annotations

from src.enums import InstallerFatalError, InstallType, NodeTier


class TestInstallType:
    """Tests for InstallType enum."""

    def test_values(self) -> None:
        assert InstallType.VENV == "venv"
        assert InstallType.CONDA == "conda"

    def test_string_comparison(self) -> None:
        """StrEnum members compare transparently with plain strings."""
        assert InstallType.VENV == "venv"
        assert InstallType("venv") is InstallType.VENV

    def test_invalid_value(self) -> None:
        import pytest
        with pytest.raises(ValueError):
            InstallType("invalid")


class TestNodeTier:
    """Tests for NodeTier enum."""

    def test_values(self) -> None:
        assert NodeTier.MINIMAL == "minimal"
        assert NodeTier.UMEAIRT == "umeairt"
        assert NodeTier.FULL == "full"

    def test_hierarchy_order(self) -> None:
        """Ensure all three tiers exist."""
        assert len(NodeTier) == 3


class TestInstallerFatalError:
    """Tests for InstallerFatalError exception."""

    def test_is_exception(self) -> None:
        assert issubclass(InstallerFatalError, Exception)

    def test_message(self) -> None:
        err = InstallerFatalError("test message")
        assert str(err) == "test message"

    def test_can_be_raised_and_caught(self) -> None:
        import pytest
        with pytest.raises(InstallerFatalError, match="fatal"):
            raise InstallerFatalError("fatal error")

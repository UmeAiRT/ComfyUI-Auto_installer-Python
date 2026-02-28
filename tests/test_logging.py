"""Tests for the logging module."""

from __future__ import annotations

from pathlib import Path

from src.utils.logging import InstallerLogger, get_logger, setup_logger


class TestInstallerLogger:
    """Tests for InstallerLogger."""

    def test_init_without_file(self) -> None:
        """Logger can be created without a file."""
        logger = InstallerLogger()
        assert logger.log_file is None
        assert logger.current_step == 0
        assert logger.total_steps == 0

    def test_init_with_file(self, tmp_log_file: Path) -> None:
        """Logger creates the log file and directory."""
        logger = InstallerLogger(log_file=tmp_log_file, total_steps=5)
        assert logger.log_file == tmp_log_file
        assert logger.total_steps == 5
        assert tmp_log_file.parent.exists()

    def test_step_counter(self, tmp_log_file: Path) -> None:
        """Step counter increments on level 0 messages."""
        logger = InstallerLogger(log_file=tmp_log_file, total_steps=3)

        assert logger.current_step == 0
        logger.step("First step")
        assert logger.current_step == 1
        logger.step("Second step")
        assert logger.current_step == 2

    def test_log_to_file(self, tmp_log_file: Path) -> None:
        """Messages are written to the log file."""
        logger = InstallerLogger(log_file=tmp_log_file)
        logger.log("Test message", level=1)

        content = tmp_log_file.read_text(encoding="utf-8")
        assert "Test message" in content

    def test_all_levels(self, tmp_log_file: Path) -> None:
        """All log levels produce output."""
        logger = InstallerLogger(log_file=tmp_log_file, total_steps=1)

        logger.log("raw", level=-2)
        logger.log("step", level=0)
        logger.log("item", level=1)
        logger.log("sub", level=2)
        logger.log("info", level=3)

        content = tmp_log_file.read_text(encoding="utf-8")
        assert "raw" in content
        assert "step" in content
        assert "item" in content
        assert "sub" in content
        assert "info" in content

    def test_convenience_methods(self, tmp_log_file: Path) -> None:
        """Convenience methods delegate correctly."""
        logger = InstallerLogger(log_file=tmp_log_file, total_steps=1)

        logger.success("ok")
        logger.warning("warn")
        logger.error("err")
        logger.info("debug")

        content = tmp_log_file.read_text(encoding="utf-8")
        assert "ok" in content
        assert "warn" in content
        assert "err" in content
        assert "debug" in content


class TestModuleLevelLogger:
    """Tests for the module-level singleton."""

    def test_setup_and_get(self, tmp_log_file: Path) -> None:
        """setup_logger creates a logger that get_logger returns."""
        created = setup_logger(log_file=tmp_log_file, total_steps=5)
        retrieved = get_logger()
        assert created is retrieved
        assert retrieved.total_steps == 5

    def test_get_creates_default(self) -> None:
        """get_logger creates a default logger if none exists."""
        # Reset the global
        import src.utils.logging as mod

        mod._default_logger = None

        logger = get_logger()
        assert logger is not None
        assert logger.total_steps == 0

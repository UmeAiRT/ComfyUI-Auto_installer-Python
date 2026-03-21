"""Tests for the commands utility module — run_and_log, get_command_version."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from src.utils.commands import CommandError, get_command_version, run_and_log

if TYPE_CHECKING:
    from pathlib import Path


class TestRunAndLog:
    """Tests for run_and_log."""

    def test_success(self) -> None:
        """Successful command returns CompletedProcess."""
        mock_result = MagicMock(returncode=0, stdout="hello\n", stderr="")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result):
            result = run_and_log("echo", ["hello"])
            assert result.returncode == 0

    def test_failure_raises_command_error(self) -> None:
        """Non-zero exit code should raise CommandError."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="some error")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result):
            with pytest.raises(CommandError) as exc_info:
                run_and_log("bad_cmd", [])
            assert exc_info.value.return_code == 1

    def test_failure_ignored(self) -> None:
        """Non-zero exit with ignore_errors=True should not raise."""
        mock_result = MagicMock(returncode=42, stdout="", stderr="oops")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result):
            result = run_and_log("bad_cmd", [], ignore_errors=True)
            assert result.returncode == 42

    def test_timeout_raises_command_error(self) -> None:
        """Subprocess timeout should raise CommandError."""
        with patch(
            "src.utils.commands.subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 10),
        ):
            with pytest.raises(CommandError) as exc_info:
                run_and_log("slow_cmd", [])
            assert "timeout" in str(exc_info.value.stderr)

    def test_file_not_found_raises_command_error(self) -> None:
        """Missing command should raise CommandError."""
        with patch(
            "src.utils.commands.subprocess.run",
            side_effect=FileNotFoundError("not found"),
        ):
            with pytest.raises(CommandError) as exc_info:
                run_and_log("missing_cmd", [])
            assert "not found" in str(exc_info.value.stderr)

    def test_custom_env(self) -> None:
        """Custom env dict should be merged with os.environ."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result) as mock_run:
            run_and_log("cmd", [], env={"MY_VAR": "test"})
            call_kwargs = mock_run.call_args[1]
            assert "MY_VAR" in call_kwargs["env"]
            assert call_kwargs["env"]["MY_VAR"] == "test"

    def test_cwd_passed(self, tmp_path: Path) -> None:
        """cwd should be forwarded to subprocess.run."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result) as mock_run:
            run_and_log("cmd", [], cwd=tmp_path)
            assert mock_run.call_args[1]["cwd"] == tmp_path

    def test_stderr_logged_on_failure(self) -> None:
        """stderr lines should be logged when command fails."""
        mock_result = MagicMock(
            returncode=1, stdout="", stderr="line1\nline2"
        )
        log = MagicMock()
        with patch("src.utils.commands.subprocess.run", return_value=mock_result), pytest.raises(CommandError):
            run_and_log("bad_cmd", [], log=log)
        assert log.error.call_count >= 3  # cmd failed + command string + stderr lines


class TestGetCommandVersion:
    """Tests for get_command_version."""

    def test_returns_version(self) -> None:
        """Should return stdout from --version."""
        mock_result = MagicMock(returncode=0, stdout="git version 2.45.0\n", stderr="")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result):
            assert get_command_version("git") == "git version 2.45.0"

    def test_returns_stderr_if_no_stdout(self) -> None:
        """Some tools print version to stderr."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="v1.0.0\n")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result):
            assert get_command_version("tool") == "v1.0.0"

    def test_returns_none_on_failure(self) -> None:
        """Should return None if the command fails."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="")
        with patch("src.utils.commands.subprocess.run", return_value=mock_result):
            assert get_command_version("nonexistent") is None

    def test_handles_file_not_found(self) -> None:
        """Should return None for missing commands."""
        with patch(
            "src.utils.commands.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            assert get_command_version("nonexistent") is None

    def test_handles_timeout(self) -> None:
        """Should return None on timeout."""
        with patch(
            "src.utils.commands.subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 10),
        ):
            assert get_command_version("slow") is None

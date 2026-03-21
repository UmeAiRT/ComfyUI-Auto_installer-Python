"""Tests for the prompts utility module."""

from __future__ import annotations

from src.utils.prompts import (
    ask_choice,
    ask_text,
    confirm,
    is_non_interactive,
    set_non_interactive,
)


class TestNonInteractiveMode:
    """Tests for non-interactive mode flag."""

    def test_default_is_interactive(self) -> None:
        set_non_interactive(False)
        assert not is_non_interactive()

    def test_set_non_interactive(self) -> None:
        set_non_interactive(True)
        assert is_non_interactive()
        set_non_interactive(False)  # cleanup


class TestAskChoiceNonInteractive:
    """Tests for ask_choice in non-interactive mode."""

    def test_returns_first_valid_answer(self) -> None:
        set_non_interactive(True)
        try:
            result = ask_choice(
                "Pick one",
                ["Option A", "Option B"],
                ["a", "b"],
            )
            assert result == "A"
        finally:
            set_non_interactive(False)


class TestConfirmNonInteractive:
    """Tests for confirm in non-interactive mode."""

    def test_returns_default_true(self) -> None:
        set_non_interactive(True)
        try:
            assert confirm("Continue?", default=True) is True
        finally:
            set_non_interactive(False)

    def test_returns_default_false(self) -> None:
        set_non_interactive(True)
        try:
            assert confirm("Continue?", default=False) is False
        finally:
            set_non_interactive(False)


class TestAskTextNonInteractive:
    """Tests for ask_text in non-interactive mode."""

    def test_returns_default(self) -> None:
        set_non_interactive(True)
        try:
            assert ask_text("Path?", default="/opt/comfyui") == "/opt/comfyui"
        finally:
            set_non_interactive(False)

    def test_returns_empty_default(self) -> None:
        set_non_interactive(True)
        try:
            assert ask_text("Path?") == ""
        finally:
            set_non_interactive(False)

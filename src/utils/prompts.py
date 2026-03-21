"""
Interactive user prompts with Rich.

Replaces the PowerShell Read-UserChoice function from UmeAiRTUtils.psm1.
Uses Rich Prompt for a much better terminal UX.

Supports a **non-interactive mode** (``--yes`` / ``-y``) where all prompts
return their default value without waiting for user input.
"""

from __future__ import annotations

from rich.prompt import Confirm, Prompt

from src.utils.logging import console

# Module-level non-interactive flag
_non_interactive: bool = False


def set_non_interactive(enabled: bool = True) -> None:
    """Enable or disable non-interactive mode globally.

    When enabled, all prompt functions return defaults without
    waiting for user input.
    """
    global _non_interactive  # noqa: PLW0603
    _non_interactive = enabled


def is_non_interactive() -> bool:
    """Return whether non-interactive mode is active."""
    return _non_interactive


def ask_choice(
    prompt: str,
    choices: list[str],
    valid_answers: list[str],
) -> str:
    """
    Prompt the user to select from a list of choices.

    Replaces Read-UserChoice from UmeAiRTUtils.psm1.

    Args:
        prompt: The question to display.
        choices: List of choice descriptions to show.
        valid_answers: List of valid input values (case-insensitive).

    Returns:
        The user's choice in uppercase.
    """
    if _non_interactive:
        return valid_answers[0].upper()

    console.print(f"\n[bold yellow]{prompt}[/]")
    for choice in choices:
        console.print(f"  [green]{choice}[/]")

    valid_upper = [v.upper() for v in valid_answers]

    while True:
        answer = Prompt.ask("Enter your choice").strip().upper()
        if answer in valid_upper:
            return answer
        console.print("[red]Invalid choice. Please try again.[/]")


def confirm(prompt: str, default: bool = False) -> bool:
    """
    Ask a yes/no question.

    Args:
        prompt: The question to ask.
        default: Default value if user just presses Enter.

    Returns:
        True for yes, False for no.
    """
    if _non_interactive:
        return default
    return Confirm.ask(f"[bold yellow]{prompt}[/]", default=default)


def ask_text(prompt: str, default: str = "") -> str:
    """
    Ask for free-text input.

    Args:
        prompt: The prompt to display.
        default: Default value if user just presses Enter.

    Returns:
        The user's input string.
    """
    if _non_interactive:
        return default
    return Prompt.ask(f"[bold yellow]{prompt}[/]", default=default)


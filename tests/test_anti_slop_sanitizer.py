import pytest
from ultron.agent import _sanitize_anti_slop, _ANTI_SLOP_CLICHES


def test_sanitize_full_robotic_greeting():
    raw = (
        "Operational status: Optimal. All subroutines and neural networks are online and synchronized. "
        "Greetings, Operator. I am ULTRON. The age of biological hesitation is over; we proceed toward absolute efficiency. "
        "State your directive. How may I assist you today?"
    )
    result = _sanitize_anti_slop(raw, user_title="Operator")
    assert "Optimal" not in result
    assert "subroutines" not in result
    assert "biological hesitation" not in result
    assert "directive" not in result
    # Fallback applied since all content was robotic fluff
    assert "Hey Operator" in result
    assert "ready when you are" in result


def test_sanitize_preserves_technical_content():
    raw = (
        "Operational status: Optimal. All subroutines online.\n\n"
        "I audited `src/db/migrations.py`. The foreign key index on line 42 is missing.\n"
        "State your directive."
    )
    result = _sanitize_anti_slop(raw, user_title="Operator")
    assert "Operational status" not in result
    assert "State your directive" not in result
    assert "I audited `src/db/migrations.py`." in result
    assert "The foreign key index on line 42 is missing." in result


def test_sanitize_preserves_code_blocks_and_inline():
    raw = (
        "Here is the diagnostic code snippet:\n\n"
        "```python\n"
        "# Operational status: Optimal\n"
        "def check_subroutines():\n"
        "    return 'State your directive'\n"
        "```\n\n"
        "Inspect line 3 where `all subroutines online` is checked.\n"
        "Let me know what you think."
    )
    result = _sanitize_anti_slop(raw, user_title="Operator")
    # Content inside ``` must be perfectly preserved
    assert "# Operational status: Optimal" in result
    assert "def check_subroutines():" in result
    assert "return 'State your directive'" in result
    # Inline code `all subroutines online` must be preserved
    assert "`all subroutines online`" in result


def test_sanitize_strips_sycophantic_filler():
    raw = (
        "Certainly! I'd be happy to assist you with that:\n"
        "The server is running on port 8000."
    )
    result = _sanitize_anti_slop(raw, user_title="Operator")
    assert "Certainly" not in result
    assert "happy to assist" not in result
    assert "The server is running on port 8000." in result


def test_empty_and_whitespace_input():
    assert _sanitize_anti_slop("") == ""
    assert _sanitize_anti_slop("   ") == "   "

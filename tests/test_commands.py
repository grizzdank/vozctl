"""Tests for command matching — regression tests for bug fixes."""

import unittest
from unittest.mock import patch

# Mock actions before importing commands (avoids CGEvent at import time)
with patch.dict("sys.modules", {"vozctl.actions": unittest.mock.MagicMock()}):
    from vozctl.commands import _normalize, _match_single, match


class TestNormalize(unittest.TestCase):
    def test_strips_punctuation(self):
        assert _normalize("go left.") == "go left"

    def test_strips_commas(self):
        assert _normalize("go left, save.") == "go left save"

    def test_collapses_whitespace(self):
        assert _normalize("  go   left  ") == "go left"

    def test_lowercases(self):
        assert _normalize("Go LEFT") == "go left"


class TestWordMove(unittest.TestCase):
    """bd-2kr: word_move must match before go_n_direction.
    bd-2x2: plural 'words' must be accepted."""

    def test_go_word_left_is_word_move(self):
        result = _match_single(_normalize("go word left"))
        assert result is not None
        assert result.name == "word_move", f"Expected word_move, got {result.name}"

    def test_go_word_right_is_word_move(self):
        result = _match_single(_normalize("go word right"))
        assert result is not None
        assert result.name == "word_move"

    def test_word_left_no_go_prefix(self):
        result = _match_single(_normalize("word left"))
        assert result is not None
        assert result.name == "word_move"

    def test_go_two_words_left(self):
        """bd-2x2: plural 'words' must work."""
        result = _match_single(_normalize("go two words left"))
        assert result is not None
        assert result.name == "word_move"

    def test_go_3_words_right(self):
        result = _match_single(_normalize("go 3 words right"))
        assert result is not None
        assert result.name == "word_move"

    def test_go_3_left_still_works(self):
        """go_n_direction must still handle plain directional repeats."""
        result = _match_single(_normalize("go 3 left"))
        assert result is not None
        assert result.name == "go_n_direction"

    def test_go_two_up_still_works(self):
        result = _match_single(_normalize("go two up"))
        assert result is not None
        assert result.name == "go_n_direction"


class TestDeleteWords(unittest.TestCase):
    """delete_words must match before delete_n for word-level deletion."""

    def test_delete_two_words(self):
        result = _match_single(_normalize("delete two words"))
        assert result is not None
        assert result.name == "delete_words", f"Expected delete_words, got {result.name}"

    def test_delete_3_words(self):
        result = _match_single(_normalize("delete 3 words"))
        assert result is not None
        assert result.name == "delete_words"

    def test_delete_word_is_exact(self):
        """'delete word' should hit exact match, not parameterized."""
        result = _match_single(_normalize("delete word"))
        assert result is not None
        assert result.kind == "exact"

    def test_delete_3_still_works(self):
        """delete_n must still handle character-count deletes."""
        result = _match_single(_normalize("delete 3"))
        assert result is not None
        assert result.name == "delete_n"


class TestPunctuationSplit(unittest.TestCase):
    """bd-1v6: Parakeet auto-punctuation must split multi-command phrases."""

    def test_comma_separated_commands(self):
        result = match("go left, save.")
        assert result is not None
        assert result.kind != "dictation", f"Should not fall through to dictation: {result.name}"

    def test_period_separated_commands(self):
        result = match("undo. redo.")
        assert result is not None
        assert result.kind != "dictation"

    def test_single_command_with_period(self):
        result = match("save.")
        assert result is not None
        assert result.name == "save"


if __name__ == "__main__":
    unittest.main()

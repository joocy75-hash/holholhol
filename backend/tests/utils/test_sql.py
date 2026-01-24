"""Tests for SQL utility functions."""

import pytest

from app.utils.sql import escape_like_pattern


class TestEscapeLikePattern:
    """Tests for escape_like_pattern function.

    These tests verify that SQL LIKE pattern special characters are properly
    escaped to prevent SQL injection attacks.
    """

    def test_escape_percentage(self):
        """Percentage sign should be escaped."""
        assert escape_like_pattern("100%") == "100\\%"

    def test_escape_underscore(self):
        """Underscore should be escaped."""
        assert escape_like_pattern("test_user") == "test\\_user"

    def test_escape_backslash(self):
        """Backslash (escape char) should be double-escaped."""
        assert escape_like_pattern("path\\to\\file") == "path\\\\to\\\\file"

    def test_escape_multiple_special_chars(self):
        """Multiple special characters should all be escaped."""
        assert escape_like_pattern("100%_off") == "100\\%\\_off"

    def test_empty_string(self):
        """Empty string should remain empty."""
        assert escape_like_pattern("") == ""

    def test_no_special_chars(self):
        """Normal text without special chars should be unchanged."""
        assert escape_like_pattern("normaltext") == "normaltext"

    def test_only_wildcards(self):
        """String with only wildcards should be fully escaped."""
        assert escape_like_pattern("%%%") == "\\%\\%\\%"
        assert escape_like_pattern("___") == "\\_\\_\\_"

    def test_custom_escape_char(self):
        """Custom escape character should work correctly."""
        result = escape_like_pattern("test%value", escape_char="!")
        assert result == "test!%value"

    def test_sql_injection_prevention(self):
        """Verify that malicious inputs are neutralized."""
        malicious_input = "%' OR '1'='1"
        escaped = escape_like_pattern(malicious_input)
        # Should escape the % and not allow SQL injection
        assert escaped == "\\%' OR '1'='1"
        assert "%" not in escaped or escaped.count("\\%") == escaped.count("%")

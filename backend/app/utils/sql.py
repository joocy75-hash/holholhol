"""SQL utility functions for safe query construction.

This module provides utilities for preventing SQL injection vulnerabilities
in dynamic queries, particularly for LIKE pattern matching.
"""


def escape_like_pattern(pattern: str, escape_char: str = "\\") -> str:
    """Escape special characters in SQL LIKE patterns to prevent injection.

    This function escapes wildcard characters (%, _) and the escape character itself
    to ensure user input is treated as literal text in LIKE queries.

    Args:
        pattern: User input search term to be escaped
        escape_char: Escape character to use (default: backslash)

    Returns:
        Escaped pattern safe for use in LIKE queries

    Examples:
        >>> escape_like_pattern("100%")
        '100\\\\%'
        >>> escape_like_pattern("test_user")
        'test\\\\_user'
        >>> escape_like_pattern("path\\\\to\\\\file")
        'path\\\\\\\\to\\\\\\\\file'
        >>> escape_like_pattern("100%_off")
        '100\\\\%\\\\_off'

    Security:
        This prevents SQL injection attacks where malicious users could use
        % or _ to perform unauthorized wildcard searches.

        Vulnerable:
            SELECT * FROM users WHERE name LIKE '%{user_input}%'
            # user_input = "%" returns all rows

        Safe:
            escaped = escape_like_pattern(user_input)
            SELECT * FROM users WHERE name LIKE '%{escaped}%' ESCAPE '\\\\'
            # user_input = "%" searches for literal "%" character
    """
    if not pattern:
        return pattern

    # Escape the escape character first to avoid double-escaping
    pattern = pattern.replace(escape_char, escape_char + escape_char)

    # Escape SQL LIKE wildcards
    pattern = pattern.replace("%", escape_char + "%")
    pattern = pattern.replace("_", escape_char + "_")

    return pattern

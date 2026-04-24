"""Placeholder parsing and template rendering utilities.

This module provides pure-Python helpers for working with ``{{ variable }}``
style placeholders used in AstrBot notification templates.  It is intentionally
kept free of any database or web-framework dependencies so it can be unit-tested
in isolation and reused across the codebase.

Public API
----------
extract_placeholders(body: str) -> List[str]
    Return the ordered, deduplicated list of variable names found in *body*.

validate_body(body: str) -> None
    Raise ``ValueError`` with a descriptive message if *body* contains any
    malformed placeholder syntax.

render_template(body: str, variables: dict) -> str
    Replace every ``{{ var }}`` token in *body* with the corresponding value
    from *variables* and return the rendered string.
"""

from __future__ import annotations

import re
from typing import Dict, List

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches a *well-formed* placeholder: {{ identifier }}
# The identifier must be a non-empty sequence of word characters (letters,
# digits, underscores) with optional surrounding whitespace inside the braces.
_VALID_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*([A-Za-z_]\w*)\s*\}\}"
)

# Matches *any* double-brace token (well-formed or not) so we can detect
# malformed ones.  We look for {{ … }} where the inner content is anything
# that is NOT a closing }}.
_ANY_DOUBLE_BRACE_RE = re.compile(
    r"\{\{(.*?)\}\}",
    re.DOTALL,
)

# Detects an *unclosed* opening {{ that has no matching }}.
_UNCLOSED_OPEN_RE = re.compile(r"\{\{(?!.*?\}\})", re.DOTALL)

# Detects a *stray* closing }} that has no matching opening {{ before it.
_STRAY_CLOSE_RE = re.compile(r"(?<!\{)\}\}")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def extract_placeholders(body: str) -> List[str]:
    """Return an ordered, deduplicated list of placeholder variable names.

    Only *valid* placeholders (``{{ identifier }}``) are returned.  Malformed
    tokens are silently ignored here — use :func:`validate_body` first if you
    need strict checking.

    Args:
        body: The raw template body string.

    Returns:
        A list of unique variable names in the order they first appear.

    Examples:
        >>> extract_placeholders("Hello {{ username }}, you have {{ count }} messages.")
        ['username', 'count']
        >>> extract_placeholders("No placeholders here.")
        []
        >>> extract_placeholders("{{ a }} and {{ a }} again")
        ['a']
    """
    seen: dict[str, None] = {}  # ordered set via insertion-ordered dict
    for match in _VALID_PLACEHOLDER_RE.finditer(body):
        name = match.group(1)
        seen[name] = None
    return list(seen.keys())


def validate_body(body: str) -> None:
    """Validate the placeholder syntax in a template body.

    Raises:
        ValueError: with a human-readable message describing the first
            syntax problem found.

    Accepted syntax:
        ``{{ identifier }}``  where *identifier* matches ``[A-Za-z_]\\w*``.

    Rejected examples:
        - ``{{ }}``            — empty identifier
        - ``{{ 123abc }}``     — identifier starts with a digit
        - ``{{ foo bar }}``    — identifier contains a space
        - ``{{ foo``           — unclosed opening brace
        - ``foo }}``           — stray closing brace
        - ``{{missing close}`` — single-brace close

    Args:
        body: The raw template body string to validate.

    Returns:
        None if the body is valid.
    """
    # 1. Detect unclosed {{ that never gets a matching }}
    if _UNCLOSED_OPEN_RE.search(body):
        raise ValueError(
            "模板语法错误：存在未闭合的 '{{' 占位符（缺少对应的 '}}'）"
        )

    # 2. Detect stray }} with no preceding {{
    #    We do this by scanning for }} that are not part of a valid {{ … }} pair.
    #    Strategy: remove all valid {{ … }} tokens, then check for remaining }}.
    stripped = _ANY_DOUBLE_BRACE_RE.sub("", body)
    if "}}" in stripped:
        raise ValueError(
            "模板语法错误：存在多余的 '}}' （没有对应的 '{{'）"
        )

    # 3. Validate the content of every {{ … }} token
    for match in _ANY_DOUBLE_BRACE_RE.finditer(body):
        inner = match.group(1)          # content between {{ and }}
        inner_stripped = inner.strip()

        if not inner_stripped:
            raise ValueError(
                f"模板语法错误：占位符 '{match.group(0)}' 的变量名不能为空"
            )

        # Must be a valid Python-style identifier
        if not re.fullmatch(r"[A-Za-z_]\w*", inner_stripped):
            raise ValueError(
                f"模板语法错误：占位符 '{match.group(0)}' 包含无效的变量名 "
                f"'{inner_stripped}'。变量名只能包含字母、数字和下划线，且不能以数字开头"
            )


def render_template(body: str, variables: Dict[str, str]) -> str:
    """Render a template by substituting ``{{ var }}`` tokens with values.

    Unknown placeholders (those present in *body* but absent from *variables*)
    are left as-is so callers can decide how to handle missing data.

    Args:
        body:      The raw template body (assumed to be syntactically valid).
        variables: A mapping of variable name → replacement value.

    Returns:
        The rendered string with all known placeholders replaced.

    Examples:
        >>> render_template("Hello {{ name }}!", {"name": "Alice"})
        'Hello Alice!'
        >>> render_template("{{ a }} + {{ b }}", {"a": "1"})
        '1 + {{ b }}'
    """
    def _replace(match: re.Match) -> str:
        name = match.group(1).strip()
        return str(variables[name]) if name in variables else match.group(0)

    return _VALID_PLACEHOLDER_RE.sub(_replace, body)

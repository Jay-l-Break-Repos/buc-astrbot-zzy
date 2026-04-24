"""Placeholder parsing, validation, and template rendering utilities.

This module provides pure-Python helpers for working with ``{{ variable }}``
style placeholders used in notification message templates.

Public API
----------
extract_placeholders(body)          -> List[str]
validate_placeholder_syntax(body)   -> List[str]   (returns list of error messages)
render_template(body, variables)    -> str
"""

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches a well-formed placeholder: {{ identifier }}
# Identifier rules: starts with a letter or underscore, followed by
# letters, digits, underscores, or dots (for nested keys like {{ user.name }}).
_VALID_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}"
)

# Matches anything that *looks* like a placeholder attempt ({{ ... }})
# but may be malformed – used for syntax validation.
_ANY_BRACE_PAIR_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)

# Identifier pattern (without surrounding braces/whitespace)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

# Maximum allowed placeholder name length
_MAX_PLACEHOLDER_NAME_LEN = 64


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def extract_placeholders(body: str) -> List[str]:
    """Return a deduplicated, ordered list of placeholder variable names.

    Only syntactically valid placeholders (``{{ identifier }}``) are returned.
    Malformed ones are silently ignored – use :func:`validate_placeholder_syntax`
    to surface errors.

    Args:
        body: The raw template body string.

    Returns:
        List of unique variable names in the order they first appear.

    Examples:
        >>> extract_placeholders("Hi {{ username }}, you have {{ count }} messages.")
        ['username', 'count']
        >>> extract_placeholders("No placeholders here.")
        []
        >>> extract_placeholders("{{ a }} {{ a }} {{ b }}")
        ['a', 'b']
    """
    seen: dict = {}
    result: List[str] = []
    for match in _VALID_PLACEHOLDER_RE.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen[name] = True
            result.append(name)
    return result


def validate_placeholder_syntax(body: str) -> List[str]:
    """Validate all placeholder-like tokens in *body* and return error messages.

    A placeholder is considered malformed when:
    - The inner content is empty or whitespace-only  (``{{  }}``)
    - The identifier contains invalid characters     (``{{ 123bad }}``)
    - The identifier starts with a digit             (``{{ 0start }}``)
    - The identifier is too long (> 64 chars)
    - The identifier contains consecutive dots       (``{{ a..b }}``)
    - The identifier starts or ends with a dot       (``{{ .a }}``, ``{{ a. }}``)

    Unmatched single braces (``{``, ``}``) are **not** flagged – they are
    treated as literal text.

    Args:
        body: The raw template body string.

    Returns:
        A list of human-readable error strings.  An empty list means the
        body is syntactically valid.

    Examples:
        >>> validate_placeholder_syntax("Hello {{ username }}!")
        []
        >>> validate_placeholder_syntax("Hello {{  }}!")
        ["占位符内容不能为空: '{{}}'"]
        >>> validate_placeholder_syntax("Hello {{ 123bad }}!")
        ["占位符名称无效 '123bad': 必须以字母或下划线开头，只能包含字母、数字、下划线和点"]
    """
    errors: List[str] = []

    for match in _ANY_BRACE_PAIR_RE.finditer(body):
        inner = match.group(1)
        raw_token = match.group(0)
        stripped = inner.strip()

        # Empty placeholder
        if not stripped:
            errors.append(f"占位符内容不能为空: '{raw_token}'")
            continue

        # Too long
        if len(stripped) > _MAX_PLACEHOLDER_NAME_LEN:
            errors.append(
                f"占位符名称过长 (最多 {_MAX_PLACEHOLDER_NAME_LEN} 个字符): '{raw_token}'"
            )
            continue

        # Leading/trailing dots
        if stripped.startswith(".") or stripped.endswith("."):
            errors.append(
                f"占位符名称不能以点号开头或结尾: '{raw_token}'"
            )
            continue

        # Consecutive dots
        if ".." in stripped:
            errors.append(
                f"占位符名称不能包含连续点号: '{raw_token}'"
            )
            continue

        # Full identifier check
        if not _IDENTIFIER_RE.match(stripped):
            errors.append(
                f"占位符名称无效 '{stripped}': 必须以字母或下划线开头，只能包含字母、数字、下划线和点"
            )

    return errors


def render_template(
    body: str,
    variables: Dict[str, str],
    *,
    missing_strategy: str = "keep",
) -> Tuple[str, List[str]]:
    """Render *body* by substituting ``{{ variable }}`` placeholders.

    Args:
        body: The raw template body string.
        variables: A mapping of variable name → replacement value.
            Values are coerced to ``str`` automatically.
        missing_strategy: Controls behaviour when a placeholder has no
            corresponding key in *variables*:

            - ``"keep"``  (default) – leave the original ``{{ var }}`` token
              unchanged in the output.
            - ``"empty"`` – replace missing placeholders with an empty string.
            - ``"error"`` – raise a :class:`KeyError` for the first missing key.

    Returns:
        A ``(rendered_text, warnings)`` tuple where *warnings* is a list of
        human-readable strings describing any missing variables (only populated
        when *missing_strategy* is ``"keep"`` or ``"empty"``).

    Raises:
        KeyError: When *missing_strategy* is ``"error"`` and a placeholder
            variable is not found in *variables*.
        ValueError: When *missing_strategy* is an unrecognised value.

    Examples:
        >>> render_template("Hi {{ name }}!", {"name": "Alice"})
        ('Hi Alice!', [])
        >>> render_template("Hi {{ name }}!", {})
        ('Hi {{ name }}!', ["变量 'name' 未提供，占位符保持原样"])
        >>> render_template("Hi {{ name }}!", {}, missing_strategy="empty")
        ('Hi !', ["变量 'name' 未提供，已替换为空字符串"])
    """
    if missing_strategy not in ("keep", "empty", "error"):
        raise ValueError(
            f"未知的 missing_strategy: '{missing_strategy}'，"
            "有效值为 'keep'、'empty'、'error'"
        )

    warnings: List[str] = []

    def _replace(match: re.Match) -> str:
        name = match.group(1)
        if name in variables:
            return str(variables[name])

        # Variable not supplied
        if missing_strategy == "error":
            raise KeyError(name)
        if missing_strategy == "empty":
            warnings.append(f"变量 '{name}' 未提供，已替换为空字符串")
            return ""
        # "keep"
        warnings.append(f"变量 '{name}' 未提供，占位符保持原样")
        return match.group(0)

    rendered = _VALID_PLACEHOLDER_RE.sub(_replace, body)
    return rendered, warnings

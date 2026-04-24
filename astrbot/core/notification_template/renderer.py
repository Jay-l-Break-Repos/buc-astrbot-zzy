"""Placeholder parsing, validation, and template rendering utilities.

This module provides pure-Python helpers for working with ``{{ variable }}``
and ``{{ variable|filter }}`` style placeholders used in notification message
templates.

Supported Jinja2-compatible filters
------------------------------------
- ``upper``              – convert to uppercase
- ``lower``              – convert to lowercase
- ``title``              – title-case
- ``capitalize``         – capitalise first character
- ``strip``              – strip leading/trailing whitespace
- ``trim``               – alias for strip
- ``default(value)``     – use *value* when the variable is missing/empty
- ``default(value,true)``– use *value* when the variable is falsy
- ``truncate(n)``        – truncate to *n* characters (appends "…")
- ``replace(old,new)``   – simple string replacement
- ``int``                – cast to int (returns 0 on failure)
- ``float``              – cast to float (returns 0.0 on failure)
- ``string``             – explicit str() cast (no-op for strings)
- ``length`` / ``count`` – length of the value string
- ``reverse``            – reverse the string
- ``urlencode``          – percent-encode the value

Public API
----------
extract_placeholders(body)          -> List[str]
validate_placeholder_syntax(body)   -> List[str]   (returns list of error messages)
render_template(body, variables)    -> str
"""

import re
import urllib.parse
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches a well-formed placeholder with optional filter chain:
#   {{ identifier }}
#   {{ identifier|filter }}
#   {{ identifier|filter(arg) }}
#   {{ identifier|filter1|filter2 }}
# Identifier rules: starts with a letter or underscore, followed by
# letters, digits, underscores, or dots (for nested keys like {{ user.name }}).
_VALID_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)"   # variable name
    r"((?:\s*\|\s*[A-Za-z_][A-Za-z0-9_]*"  # optional filter(s)
    r"(?:\([^)]*\))?)*)"                    # optional filter args
    r"\s*\}\}"
)

# Matches anything that *looks* like a placeholder attempt ({{ ... }})
# but may be malformed – used for syntax validation.
_ANY_BRACE_PAIR_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)

# Identifier pattern (without surrounding braces/whitespace/filters)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")

# Maximum allowed placeholder name length
_MAX_PLACEHOLDER_NAME_LEN = 64

# ---------------------------------------------------------------------------
# Built-in filter implementations
# ---------------------------------------------------------------------------

def _parse_filter_chain(filter_str: str) -> List[Tuple[str, List[str]]]:
    """Parse a filter chain string like ``|upper|default("N/A")|truncate(10)``.

    Returns a list of ``(filter_name, [arg, ...])`` tuples.
    """
    filters: List[Tuple[str, List[str]]] = []
    # Split on pipe, skip empty segments
    for segment in filter_str.split("|"):
        segment = segment.strip()
        if not segment:
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\(([^)]*)\))?$", segment)
        if not m:
            continue
        name = m.group(1)
        raw_args = m.group(2)
        args: List[str] = []
        if raw_args is not None:
            for arg in raw_args.split(","):
                arg = arg.strip().strip("'\"")
                args.append(arg)
        filters.append((name, args))
    return filters


def _apply_filter(value: str, name: str, args: List[str]) -> str:
    """Apply a single named filter to *value* and return the result."""
    if name == "upper":
        return value.upper()
    if name == "lower":
        return value.lower()
    if name == "title":
        return value.title()
    if name == "capitalize":
        return value.capitalize()
    if name in ("strip", "trim"):
        return value.strip()
    if name == "reverse":
        return value[::-1]
    if name in ("length", "count"):
        return str(len(value))
    if name == "string":
        return str(value)
    if name == "int":
        try:
            return str(int(value))
        except (ValueError, TypeError):
            return "0"
    if name == "float":
        try:
            return str(float(value))
        except (ValueError, TypeError):
            return "0.0"
    if name == "urlencode":
        return urllib.parse.quote(value, safe="")
    if name == "default":
        # default(fallback) or default(fallback, true)
        fallback = args[0] if args else ""
        boolean_mode = len(args) >= 2 and args[1].lower() in ("true", "1", "yes")
        if boolean_mode:
            return value if value else fallback
        return value if value != "" else fallback
    if name == "truncate":
        try:
            n = int(args[0]) if args else 255
        except (ValueError, IndexError):
            n = 255
        return value if len(value) <= n else value[:n] + "…"
    if name == "replace":
        if len(args) >= 2:
            return value.replace(args[0], args[1])
        return value
    # Unknown filter – return value unchanged
    return value


def _apply_filter_chain(value: str, filter_str: str) -> str:
    """Apply all filters in *filter_str* to *value* sequentially."""
    for name, args in _parse_filter_chain(filter_str):
        value = _apply_filter(value, name, args)
    return value


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def extract_placeholders(body: str) -> List[str]:
    """Return a deduplicated, ordered list of placeholder variable names.

    Only syntactically valid placeholders (``{{ identifier }}``) are returned.
    Malformed ones are silently ignored – use :func:`validate_placeholder_syntax`
    to surface errors.  Filter expressions (``{{ name|upper }}``) are stripped;
    only the variable name is returned.

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
        >>> extract_placeholders("{{ name|upper }}")
        ['name']
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

    Filter expressions (``{{ name|upper }}``) are validated for the variable
    name part only; filter names themselves are not validated here.

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

        # Strip filter chain to validate only the variable name part
        var_part = stripped.split("|")[0].strip()

        # Too long
        if len(var_part) > _MAX_PLACEHOLDER_NAME_LEN:
            errors.append(
                f"占位符名称过长 (最多 {_MAX_PLACEHOLDER_NAME_LEN} 个字符): '{raw_token}'"
            )
            continue

        # Leading/trailing dots
        if var_part.startswith(".") or var_part.endswith("."):
            errors.append(
                f"占位符名称不能以点号开头或结尾: '{raw_token}'"
            )
            continue

        # Consecutive dots
        if ".." in var_part:
            errors.append(
                f"占位符名称不能包含连续点号: '{raw_token}'"
            )
            continue

        # Full identifier check
        if not _IDENTIFIER_RE.match(var_part):
            errors.append(
                f"占位符名称无效 '{var_part}': 必须以字母或下划线开头，只能包含字母、数字、下划线和点"
            )

    return errors


def render_template(
    body: str,
    variables: Dict[str, Any],
    *,
    missing_strategy: str = "keep",
) -> Tuple[str, List[str]]:
    """Render *body* by substituting ``{{ variable }}`` placeholders.

    Supports Jinja2-compatible filter syntax:
    - ``{{ name|upper }}``
    - ``{{ count|default("0") }}``
    - ``{{ username|upper|truncate(20) }}``

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
        >>> render_template("Hi {{ name|upper }}!", {"name": "alice"})
        ('Hi ALICE!', [])
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
        filter_str = match.group(2) or ""

        if name in variables:
            value = str(variables[name])
            if filter_str:
                value = _apply_filter_chain(value, filter_str)
            return value

        # Variable not supplied – check if default filter provides a fallback
        if filter_str:
            for fname, fargs in _parse_filter_chain(filter_str):
                if fname == "default" and fargs:
                    return fargs[0]

        # No default available
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

"""Template engine for AstrBot notification templates.

Provides two public functions:

    extract_placeholders(body: str) -> List[str]
        Return the list of unique placeholder names found in *body*,
        preserving first-occurrence order.  Raises ``TemplateSyntaxError``
        if any placeholder name is not a valid Python identifier.

    render_template(body: str, variables: Dict[str, str]) -> str
        Substitute every ``{{ name }}`` occurrence in *body* with the
        matching value from *variables*.  Missing keys are left as-is
        (i.e. the ``{{ name }}`` token is kept verbatim) so callers can
        do partial renders.  Raises ``TemplateSyntaxError`` for invalid
        placeholder syntax.

Both functions share the same regex so the validation rules are
identical between extraction and rendering.

Placeholder syntax
------------------
A placeholder is ``{{`` followed by optional whitespace, a *name*,
optional whitespace, then ``}}``.  The *name* must match
``[A-Za-z_][A-Za-z0-9_]*`` (i.e. a valid Python identifier).

Valid examples
~~~~~~~~~~~~~~
    {{ username }}
    {{message}}
    {{ order_id }}
    {{ item123 }}

Invalid examples (raise TemplateSyntaxError)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    {{ 123abc }}   – starts with a digit
    {{ my-var }}   – contains a hyphen
    {{ }}          – empty name
    {{ a b }}      – contains a space inside the name
"""

import re
from typing import Dict, List

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class TemplateSyntaxError(ValueError):
    """Raised when a template body contains an invalid placeholder."""


# ---------------------------------------------------------------------------
# Internal regex
# ---------------------------------------------------------------------------

# Matches ANY {{ ... }} token (including malformed ones) so we can give a
# helpful error message for the bad ones rather than silently ignoring them.
_ANY_TOKEN_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)

# A valid placeholder name: Python identifier rules.
_VALID_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_tokens(body: str) -> List[str]:
    """Return placeholder names in order of first appearance.

    Raises ``TemplateSyntaxError`` for any token whose name is not a
    valid identifier.
    """
    seen: dict = {}
    result: List[str] = []

    for match in _ANY_TOKEN_RE.finditer(body):
        raw = match.group(1)          # everything between {{ and }}
        name = raw.strip()

        if not name:
            raise TemplateSyntaxError(
                f"模板语法错误: 空占位符 '{match.group(0)}' — 占位符名称不能为空"
            )

        if not _VALID_NAME_RE.match(name):
            raise TemplateSyntaxError(
                f"模板语法错误: 无效的占位符名称 '{name}' — "
                "占位符名称只能包含字母、数字和下划线，且不能以数字开头"
            )

        if name not in seen:
            seen[name] = True
            result.append(name)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_placeholders(body: str) -> List[str]:
    """Extract all unique placeholder names from *body*.

    Parameters
    ----------
    body:
        The template body string, e.g. ``"Hello {{ username }}!"``.

    Returns
    -------
    List[str]
        Unique placeholder names in first-occurrence order, e.g.
        ``["username"]``.

    Raises
    ------
    TemplateSyntaxError
        If any ``{{ ... }}`` token contains an invalid or empty name.
    TypeError
        If *body* is not a string.
    """
    if not isinstance(body, str):
        raise TypeError(f"body 必须是字符串，而不是 {type(body).__name__}")
    return _parse_tokens(body)


def render_template(body: str, variables: Dict[str, str]) -> str:
    """Render *body* by substituting ``{{ name }}`` tokens with *variables*.

    Parameters
    ----------
    body:
        The template body string.
    variables:
        A mapping of placeholder name → replacement value.  Extra keys
        (not present in the template) are silently ignored.  Missing
        keys (present in the template but not in *variables*) are left
        as their original ``{{ name }}`` token.

    Returns
    -------
    str
        The rendered string.

    Raises
    ------
    TemplateSyntaxError
        If the template contains invalid placeholder syntax.
    TypeError
        If *body* is not a string or *variables* is not a dict.
    """
    if not isinstance(body, str):
        raise TypeError(f"body 必须是字符串，而不是 {type(body).__name__}")
    if not isinstance(variables, dict):
        raise TypeError(f"variables 必须是字典，而不是 {type(variables).__name__}")

    # Validate all tokens first (raises TemplateSyntaxError on bad syntax)
    _parse_tokens(body)

    def _replace(match: re.Match) -> str:
        name = match.group(1).strip()
        # Leave unknown placeholders verbatim
        return str(variables[name]) if name in variables else match.group(0)

    return _ANY_TOKEN_RE.sub(_replace, body)

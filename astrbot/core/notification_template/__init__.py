"""notification_template sub-package.

Exposes the three public helpers at the package level for convenience:

    from astrbot.core.notification_template import (
        extract_placeholders,
        validate_placeholder_syntax,
        render_template,
    )
"""

from .renderer import extract_placeholders, validate_placeholder_syntax, render_template

__all__ = [
    "extract_placeholders",
    "validate_placeholder_syntax",
    "render_template",
]

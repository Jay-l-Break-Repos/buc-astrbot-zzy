"""
Tests for Step 2: placeholder parsing, validation, and template rendering.

Covers:
  - extract_placeholders()
  - validate_placeholder_syntax()
  - render_template()
  - Integration: validation on create/update via SQLiteDatabase

Run with:
    python -m pytest tests/test_template_rendering.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrbot.core.notification_template import (
    extract_placeholders,
    validate_placeholder_syntax,
    render_template,
)
from astrbot.core.db.sqlite import SQLiteDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db(tmp_path):
    """Fresh SQLiteDatabase for integration tests."""
    return SQLiteDatabase(str(tmp_path / "test.db"))


# ===========================================================================
# extract_placeholders
# ===========================================================================


class TestExtractPlaceholders:
    def test_single_placeholder(self):
        assert extract_placeholders("Hello {{ username }}!") == ["username"]

    def test_multiple_placeholders(self):
        result = extract_placeholders("{{ greeting }}, {{ name }}. You have {{ count }} messages.")
        assert result == ["greeting", "name", "count"]

    def test_deduplication_preserves_order(self):
        result = extract_placeholders("{{ a }} {{ b }} {{ a }} {{ c }} {{ b }}")
        assert result == ["a", "b", "c"]

    def test_no_placeholders(self):
        assert extract_placeholders("No placeholders here.") == []

    def test_empty_string(self):
        assert extract_placeholders("") == []

    def test_extra_whitespace_inside_braces(self):
        assert extract_placeholders("{{  username  }}") == ["username"]
        assert extract_placeholders("{{username}}") == ["username"]

    def test_dotted_identifier(self):
        result = extract_placeholders("{{ user.name }} and {{ user.email }}")
        assert result == ["user.name", "user.email"]

    def test_underscore_identifier(self):
        assert extract_placeholders("{{ first_name }}") == ["first_name"]

    def test_mixed_valid_and_invalid(self):
        result = extract_placeholders("{{ valid }} and {{ 123bad }}")
        assert result == ["valid"]

    def test_multiline_body(self):
        body = "Line 1: {{ var1 }}\nLine 2: {{ var2 }}\nLine 3: {{ var1 }}"
        assert extract_placeholders(body) == ["var1", "var2"]

    def test_adjacent_placeholders(self):
        assert extract_placeholders("{{ a }}{{ b }}") == ["a", "b"]

    def test_placeholder_in_url_like_string(self):
        body = "https://example.com/users/{{ user_id }}/profile"
        assert extract_placeholders(body) == ["user_id"]


# ===========================================================================
# validate_placeholder_syntax
# ===========================================================================


class TestValidatePlaceholderSyntax:
    def test_valid_simple(self):
        assert validate_placeholder_syntax("Hello {{ username }}!") == []

    def test_valid_multiple(self):
        assert validate_placeholder_syntax("{{ a }} {{ b }} {{ c }}") == []

    def test_valid_dotted(self):
        assert validate_placeholder_syntax("{{ user.name }}") == []

    def test_valid_underscore(self):
        assert validate_placeholder_syntax("{{ first_name }}") == []

    def test_valid_no_placeholders(self):
        assert validate_placeholder_syntax("Plain text.") == []

    def test_valid_empty_string(self):
        assert validate_placeholder_syntax("") == []

    def test_empty_placeholder(self):
        errors = validate_placeholder_syntax("Hello {{  }}!")
        assert len(errors) == 1
        assert "不能为空" in errors[0]

    def test_empty_placeholder_no_space(self):
        errors = validate_placeholder_syntax("Hello {{}}!")
        assert len(errors) == 1
        assert "不能为空" in errors[0]

    def test_starts_with_digit(self):
        errors = validate_placeholder_syntax("{{ 123bad }}")
        assert len(errors) == 1
        assert "无效" in errors[0]

    def test_starts_with_digit_pure_number(self):
        errors = validate_placeholder_syntax("{{ 42 }}")
        assert len(errors) == 1

    def test_invalid_special_chars(self):
        errors = validate_placeholder_syntax("{{ user-name }}")
        assert len(errors) == 1
        assert "无效" in errors[0]

    def test_invalid_space_inside(self):
        errors = validate_placeholder_syntax("{{ user name }}")
        assert len(errors) == 1

    def test_leading_dot(self):
        errors = validate_placeholder_syntax("{{ .name }}")
        assert len(errors) == 1
        assert "点号" in errors[0]

    def test_trailing_dot(self):
        errors = validate_placeholder_syntax("{{ name. }}")
        assert len(errors) == 1
        assert "点号" in errors[0]

    def test_consecutive_dots(self):
        errors = validate_placeholder_syntax("{{ a..b }}")
        assert len(errors) == 1
        assert "连续点号" in errors[0]

    def test_too_long_name(self):
        long_name = "a" * 65
        errors = validate_placeholder_syntax("{{ " + long_name + " }}")
        assert len(errors) == 1
        assert "过长" in errors[0]

    def test_exactly_max_length_is_valid(self):
        name = "a" * 64
        errors = validate_placeholder_syntax("{{ " + name + " }}")
        assert errors == []

    def test_multiple_errors(self):
        body = "{{ }} {{ 123 }} {{ valid }}"
        errors = validate_placeholder_syntax(body)
        assert len(errors) == 2

    def test_single_braces_ignored(self):
        assert validate_placeholder_syntax("{ not a placeholder }") == []
        assert validate_placeholder_syntax("price: $5 {discount}") == []

    def test_valid_with_numbers_after_letter(self):
        assert validate_placeholder_syntax("{{ var1 }}") == []
        assert validate_placeholder_syntax("{{ _private }}") == []

    def test_block_tag_is_invalid(self):
        """{% ... %} Jinja2 block tags are not supported."""
        errors = validate_placeholder_syntax("{% if user %}hi{% endif %}")
        assert len(errors) >= 1

    def test_unclosed_brace_is_invalid(self):
        """{{ without matching }} is invalid."""
        errors = validate_placeholder_syntax("Hello {{ username }%, broken")
        assert len(errors) >= 1

    def test_mixed_block_and_unclosed_is_invalid(self):
        """The exact body from the spec invalid-syntax test."""
        errors = validate_placeholder_syntax(
            "Hello {{ username }%, this is broken {% if %}"
        )
        assert len(errors) >= 1


# ===========================================================================
# render_template
# ===========================================================================


class TestRenderTemplate:
    def test_simple_render(self):
        rendered, warnings = render_template("Hello {{ name }}!", {"name": "Alice"})
        assert rendered == "Hello Alice!"
        assert warnings == []

    def test_multiple_vars(self):
        body = "{{ greeting }}, {{ name }}. You have {{ count }} messages."
        rendered, warnings = render_template(body, {"greeting": "Hi", "name": "Bob", "count": "5"})
        assert rendered == "Hi, Bob. You have 5 messages."
        assert warnings == []

    def test_repeated_placeholder_replaced_all(self):
        rendered, _ = render_template("{{ x }} + {{ x }} = {{ y }}", {"x": "1", "y": "2"})
        assert rendered == "1 + 1 = 2"

    def test_no_placeholders(self):
        rendered, warnings = render_template("Plain text.", {})
        assert rendered == "Plain text."
        assert warnings == []

    def test_empty_body(self):
        rendered, warnings = render_template("", {"a": "b"})
        assert rendered == ""
        assert warnings == []

    def test_value_coerced_to_str(self):
        rendered, _ = render_template("Count: {{ n }}", {"n": 42})
        assert rendered == "Count: 42"

    def test_dotted_key(self):
        rendered, _ = render_template("{{ user.name }}", {"user.name": "Carol"})
        assert rendered == "Carol"

    def test_missing_keep_default(self):
        rendered, warnings = render_template("Hi {{ name }}!", {})
        assert rendered == "Hi {{ name }}!"
        assert len(warnings) == 1

    def test_missing_keep_explicit(self):
        rendered, warnings = render_template("Hi {{ name }}!", {}, missing_strategy="keep")
        assert rendered == "Hi {{ name }}!"
        assert len(warnings) == 1

    def test_missing_multiple_keep(self):
        rendered, warnings = render_template("{{ a }} {{ b }}", {})
        assert "{{ a }}" in rendered
        assert "{{ b }}" in rendered
        assert len(warnings) == 2

    def test_missing_empty(self):
        rendered, warnings = render_template("Hi {{ name }}!", {}, missing_strategy="empty")
        assert rendered == "Hi !"
        assert len(warnings) == 1

    def test_missing_empty_multiple(self):
        rendered, warnings = render_template("{{ a }}-{{ b }}", {}, missing_strategy="empty")
        assert rendered == "-"
        assert len(warnings) == 2

    def test_missing_error_raises(self):
        with pytest.raises(KeyError) as exc_info:
            render_template("Hi {{ name }}!", {}, missing_strategy="error")
        assert "name" in str(exc_info.value)

    def test_missing_error_no_raise_when_all_provided(self):
        rendered, warnings = render_template("Hi {{ name }}!", {"name": "Dave"}, missing_strategy="error")
        assert rendered == "Hi Dave!"
        assert warnings == []

    def test_invalid_strategy_raises_value_error(self):
        with pytest.raises(ValueError, match="未知的 missing_strategy"):
            render_template("{{ x }}", {}, missing_strategy="invalid")

    def test_partial_substitution(self):
        rendered, warnings = render_template("{{ a }} {{ b }} {{ c }}", {"a": "1", "c": "3"})
        assert rendered == "1 {{ b }} 3"
        assert len(warnings) == 1

    def test_value_with_special_chars(self):
        rendered, _ = render_template("Message: {{ msg }}", {"msg": "Hello <World> & 'friends'"})
        assert rendered == "Message: Hello <World> & 'friends'"

    def test_value_with_braces(self):
        rendered, _ = render_template("{{ val }}", {"val": "{{ not_a_placeholder }}"})
        assert rendered == "{{ not_a_placeholder }}"

    def test_multiline_body(self):
        body = "Dear {{ name }},\n\nYour order {{ order_id }} is ready."
        rendered, _ = render_template(body, {"name": "Eve", "order_id": "ORD-001"})
        assert rendered == "Dear Eve,\n\nYour order ORD-001 is ready."

    def test_unicode_values(self):
        rendered, _ = render_template("你好 {{ name }}！", {"name": "世界"})
        assert rendered == "你好 世界！"


# ===========================================================================
# Integration: validation + DB
# ===========================================================================


class TestValidationIntegration:
    """Ensure that validate_placeholder_syntax can be used as a gate before DB ops."""

    def test_valid_body_can_be_stored(self, db):
        errors = validate_placeholder_syntax("Hi {{ username }}, you have {{ count }} items.")
        assert errors == []
        tpl = db.create_notification_template(name="valid_tpl", body="Hi {{ username }}")
        assert tpl.id > 0

    def test_invalid_body_detected_before_store(self, db):
        body = "Hi {{ 123bad }} and {{  }}"
        errors = validate_placeholder_syntax(body)
        assert len(errors) == 2

    def test_extract_after_store_and_retrieve(self, db):
        body = "Hello {{ first_name }} {{ last_name }}, ref: {{ ref_id }}"
        tpl = db.create_notification_template(name="multi_var", body=body)
        fetched = db.get_notification_template_by_id(tpl.id)
        placeholders = extract_placeholders(fetched.body)
        assert placeholders == ["first_name", "last_name", "ref_id"]

    def test_render_after_retrieve(self, db):
        body = "Order {{ order_id }} for {{ customer }} is {{ status }}."
        db.create_notification_template(name="order_tpl", body=body)
        templates = db.get_notification_templates()
        tpl = templates[0]
        rendered, warnings = render_template(
            tpl.body,
            {"order_id": "ORD-42", "customer": "Alice", "status": "shipped"},
        )
        assert rendered == "Order ORD-42 for Alice is shipped."

    def test_render_with_missing_var_keep(self, db):
        body = "Hi {{ name }}, your code is {{ code }}."
        tpl = db.create_notification_template(name="code_tpl", body=body)
        fetched = db.get_notification_templates()[0]
        rendered, warnings = render_template(fetched.body, {"name": "Bob"})
        assert "Bob" in rendered
        assert "{{ code }}" in rendered
        assert len(warnings) == 1

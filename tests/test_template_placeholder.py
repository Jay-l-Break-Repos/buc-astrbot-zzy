"""
Tests for Step 2 — placeholder parsing, validation, and template preview.

Covers:
  - astrbot.core.template.placeholder  (extract_placeholders, validate_body, render_template)
  - Integration with SQLiteDatabase     (preview via the helper functions)

Run with:
    python -m pytest tests/test_template_placeholder.py -v
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrbot.core.template.placeholder import (
    extract_placeholders,
    validate_body,
    render_template,
)
from astrbot.core.db.sqlite import SQLiteDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """Return a fresh SQLiteDatabase backed by a temporary file."""
    return SQLiteDatabase(str(tmp_path / "test_astrbot.db"))


# ===========================================================================
# extract_placeholders
# ===========================================================================

class TestExtractPlaceholders:

    def test_single_placeholder(self):
        assert extract_placeholders("Hello {{ username }}!") == ["username"]

    def test_multiple_placeholders(self):
        result = extract_placeholders("{{ greeting }}, {{ name }}. You have {{ count }} messages.")
        assert result == ["greeting", "name", "count"]

    def test_no_placeholders(self):
        assert extract_placeholders("No placeholders here.") == []

    def test_empty_string(self):
        assert extract_placeholders("") == []

    def test_duplicate_placeholders_deduplicated(self):
        result = extract_placeholders("{{ a }} and {{ a }} and {{ b }}")
        assert result == ["a", "b"]

    def test_order_preserved(self):
        result = extract_placeholders("{{ z }} {{ a }} {{ m }}")
        assert result == ["z", "a", "m"]

    def test_extra_whitespace_inside_braces(self):
        # {{ username }} with varying internal whitespace
        assert extract_placeholders("{{  username  }}") == ["username"]
        assert extract_placeholders("{{username}}") == ["username"]

    def test_underscore_in_name(self):
        assert extract_placeholders("{{ user_name }}") == ["user_name"]

    def test_leading_underscore_in_name(self):
        assert extract_placeholders("{{ _private }}") == ["_private"]

    def test_alphanumeric_name(self):
        assert extract_placeholders("{{ var123 }}") == ["var123"]

    def test_multiline_body(self):
        body = "Line 1: {{ a }}\nLine 2: {{ b }}\nLine 3: {{ a }}"
        assert extract_placeholders(body) == ["a", "b"]

    def test_invalid_placeholders_ignored(self):
        # {{ }} and {{ 123bad }} are not valid — should be ignored by extract
        body = "{{ }} {{ 123bad }} {{ valid }}"
        assert extract_placeholders(body) == ["valid"]

    def test_placeholder_adjacent_to_text(self):
        assert extract_placeholders("prefix{{ x }}suffix") == ["x"]


# ===========================================================================
# validate_body
# ===========================================================================

class TestValidateBody:

    # --- valid bodies ---

    def test_valid_no_placeholders(self):
        validate_body("Just plain text.")  # should not raise

    def test_valid_single_placeholder(self):
        validate_body("Hello {{ username }}!")

    def test_valid_multiple_placeholders(self):
        validate_body("{{ greeting }}, {{ name }}. Count: {{ count }}")

    def test_valid_underscore_name(self):
        validate_body("{{ user_name }}")

    def test_valid_leading_underscore(self):
        validate_body("{{ _var }}")

    def test_valid_alphanumeric(self):
        validate_body("{{ item99 }}")

    def test_valid_extra_whitespace(self):
        validate_body("{{  spaced  }}")

    def test_valid_empty_body(self):
        validate_body("")  # no placeholders, no errors

    # --- invalid bodies ---

    def test_invalid_empty_placeholder(self):
        with pytest.raises(ValueError, match="变量名不能为空"):
            validate_body("{{ }}")

    def test_invalid_empty_placeholder_no_space(self):
        with pytest.raises(ValueError, match="变量名不能为空"):
            validate_body("{{}}")

    def test_invalid_starts_with_digit(self):
        with pytest.raises(ValueError, match="无效的变量名"):
            validate_body("{{ 123abc }}")

    def test_invalid_contains_space(self):
        with pytest.raises(ValueError, match="无效的变量名"):
            validate_body("{{ foo bar }}")

    def test_invalid_contains_hyphen(self):
        with pytest.raises(ValueError, match="无效的变量名"):
            validate_body("{{ foo-bar }}")

    def test_invalid_contains_dot(self):
        with pytest.raises(ValueError, match="无效的变量名"):
            validate_body("{{ foo.bar }}")

    def test_invalid_unclosed_open(self):
        with pytest.raises(ValueError, match="未闭合"):
            validate_body("Hello {{ username")

    def test_invalid_unclosed_open_partial(self):
        with pytest.raises(ValueError, match="未闭合"):
            validate_body("{{ valid }} and {{ unclosed")

    def test_invalid_stray_close(self):
        with pytest.raises(ValueError, match="多余的"):
            validate_body("Hello }} world")

    def test_invalid_stray_close_after_valid(self):
        with pytest.raises(ValueError, match="多余的"):
            validate_body("{{ valid }} and stray }}")

    def test_invalid_single_brace_close(self):
        # "{{missing close}" — has {{ but only one } at the end
        with pytest.raises(ValueError):
            validate_body("{{missing close}")

    def test_invalid_digit_only_name(self):
        with pytest.raises(ValueError, match="无效的变量名"):
            validate_body("{{ 999 }}")

    def test_invalid_special_chars(self):
        with pytest.raises(ValueError, match="无效的变量名"):
            validate_body("{{ @user }}")

    def test_mixed_valid_and_invalid(self):
        # Even if one placeholder is valid, an invalid one should still raise
        with pytest.raises(ValueError):
            validate_body("{{ valid }} and {{ 123bad }}")


# ===========================================================================
# render_template
# ===========================================================================

class TestRenderTemplate:

    def test_single_substitution(self):
        assert render_template("Hello {{ name }}!", {"name": "Alice"}) == "Hello Alice!"

    def test_multiple_substitutions(self):
        result = render_template(
            "{{ greeting }}, {{ name }}!",
            {"greeting": "Hi", "name": "Bob"},
        )
        assert result == "Hi, Bob!"

    def test_no_placeholders(self):
        assert render_template("Plain text.", {}) == "Plain text."

    def test_empty_variables_leaves_placeholders(self):
        result = render_template("Hello {{ name }}!", {})
        assert result == "Hello {{ name }}!"

    def test_unknown_placeholder_left_unchanged(self):
        result = render_template("{{ a }} + {{ b }}", {"a": "1"})
        assert result == "1 + {{ b }}"

    def test_repeated_placeholder_all_replaced(self):
        result = render_template("{{ x }} and {{ x }}", {"x": "hello"})
        assert result == "hello and hello"

    def test_numeric_value(self):
        result = render_template("Count: {{ n }}", {"n": 42})
        assert result == "Count: 42"

    def test_empty_string_value(self):
        result = render_template("{{ a }}{{ b }}", {"a": "", "b": "B"})
        assert result == "B"

    def test_extra_whitespace_in_placeholder(self):
        result = render_template("{{  name  }}", {"name": "Alice"})
        assert result == "Alice"

    def test_multiline_body(self):
        body = "Line 1: {{ a }}\nLine 2: {{ b }}"
        result = render_template(body, {"a": "foo", "b": "bar"})
        assert result == "Line 1: foo\nLine 2: bar"

    def test_special_chars_in_value(self):
        result = render_template("{{ msg }}", {"msg": "Hello <World> & 'everyone'"})
        assert result == "Hello <World> & 'everyone'"

    def test_unicode_value(self):
        result = render_template("{{ greeting }}", {"greeting": "你好"})
        assert result == "你好"

    def test_empty_body(self):
        assert render_template("", {"x": "y"}) == ""


# ===========================================================================
# Integration: placeholder utilities + SQLiteDatabase
# ===========================================================================

class TestPlaceholderIntegration:
    """Verify that placeholder utilities work correctly with real DB templates."""

    def test_extract_from_stored_template(self, db):
        tpl = db.create_notification_template(
            name="welcome",
            body="Hello {{ username }}, welcome to {{ platform }}!",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        placeholders = extract_placeholders(fetched.body)
        assert placeholders == ["username", "platform"]

    def test_render_stored_template(self, db):
        tpl = db.create_notification_template(
            name="alert",
            body="Alert: {{ message }} (severity: {{ level }})",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        rendered = render_template(fetched.body, {"message": "disk full", "level": "high"})
        assert rendered == "Alert: disk full (severity: high)"

    def test_validate_stored_template(self, db):
        tpl = db.create_notification_template(
            name="valid_tpl",
            body="{{ a }} and {{ b }}",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        validate_body(fetched.body)  # should not raise

    def test_preview_with_all_variables(self, db):
        tpl = db.create_notification_template(
            name="full_preview",
            body="Hi {{ name }}, you have {{ count }} new messages.",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        validate_body(fetched.body)
        all_vars = extract_placeholders(fetched.body)
        variables = {"name": "Charlie", "count": "5"}
        rendered = render_template(fetched.body, variables)
        missing = [p for p in all_vars if p not in variables]

        assert rendered == "Hi Charlie, you have 5 new messages."
        assert missing == []

    def test_preview_with_missing_variables(self, db):
        tpl = db.create_notification_template(
            name="partial_preview",
            body="{{ greeting }}, {{ name }}!",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        variables = {"greeting": "Hello"}
        rendered = render_template(fetched.body, variables)
        all_vars = extract_placeholders(fetched.body)
        missing = [p for p in all_vars if p not in variables]

        assert rendered == "Hello, {{ name }}!"
        assert missing == ["name"]

    def test_preview_no_variables_needed(self, db):
        tpl = db.create_notification_template(
            name="static_tpl",
            body="This template has no placeholders.",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        validate_body(fetched.body)
        rendered = render_template(fetched.body, {})
        assert rendered == "This template has no placeholders."
        assert extract_placeholders(fetched.body) == []

    def test_validate_rejects_bad_body_before_preview(self, db):
        # Simulate what the API layer does: validate before rendering
        bad_body = "Hello {{ }}, how are you?"
        with pytest.raises(ValueError, match="变量名不能为空"):
            validate_body(bad_body)

    def test_extract_deduplication_in_stored_template(self, db):
        tpl = db.create_notification_template(
            name="dedup_tpl",
            body="{{ x }} then {{ y }} then {{ x }} again",
        )
        fetched = db.get_notification_template_by_id(tpl.id)
        assert extract_placeholders(fetched.body) == ["x", "y"]

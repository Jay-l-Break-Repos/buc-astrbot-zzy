"""
Tests for the NotificationTemplate model and SQLiteDatabase CRUD methods.

Run with:
    python -m pytest tests/test_notification_template.py -v
"""

import os
import sys
import tempfile
import time
import pytest

# ---------------------------------------------------------------------------
# Make sure the repo root is on sys.path so we can import astrbot.*
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrbot.core.db.po import NotificationTemplate
from astrbot.core.db.sqlite import SQLiteDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """Return a fresh SQLiteDatabase backed by a temporary file."""
    db_file = str(tmp_path / "test_astrbot.db")
    return SQLiteDatabase(db_file)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestNotificationTemplateModel:
    def test_dataclass_fields(self):
        tpl = NotificationTemplate(id=1, name="welcome", body="Hello {{ username }}!")
        assert tpl.id == 1
        assert tpl.name == "welcome"
        assert tpl.body == "Hello {{ username }}!"
        assert tpl.created_at == 0
        assert tpl.updated_at == 0

    def test_dataclass_with_timestamps(self):
        now = int(time.time())
        tpl = NotificationTemplate(id=2, name="alert", body="{{ message }}", created_at=now, updated_at=now)
        assert tpl.created_at == now
        assert tpl.updated_at == now


# ---------------------------------------------------------------------------
# Database CRUD tests
# ---------------------------------------------------------------------------

class TestNotificationTemplateCRUD:

    # --- create ---

    def test_create_returns_template(self, db):
        tpl = db.create_notification_template(name="greet", body="Hi {{ username }}")
        assert isinstance(tpl, NotificationTemplate)
        assert tpl.id is not None and tpl.id > 0
        assert tpl.name == "greet"
        assert tpl.body == "Hi {{ username }}"
        assert tpl.created_at > 0
        assert tpl.updated_at > 0

    def test_create_duplicate_name_raises(self, db):
        db.create_notification_template(name="dup", body="body1")
        with pytest.raises(ValueError, match="已存在"):
            db.create_notification_template(name="dup", body="body2")

    def test_create_multiple_templates(self, db):
        db.create_notification_template(name="t1", body="body1")
        db.create_notification_template(name="t2", body="body2")
        templates = db.get_notification_templates()
        assert len(templates) == 2

    # --- list ---

    def test_list_empty(self, db):
        assert db.get_notification_templates() == []

    def test_list_ordered_by_created_at(self, db):
        db.create_notification_template(name="first", body="a")
        time.sleep(0.01)
        db.create_notification_template(name="second", body="b")
        templates = db.get_notification_templates()
        assert templates[0].name == "first"
        assert templates[1].name == "second"

    # --- get by id ---

    def test_get_by_id_existing(self, db):
        created = db.create_notification_template(name="fetch_me", body="content")
        fetched = db.get_notification_template_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "fetch_me"
        assert fetched.body == "content"

    def test_get_by_id_nonexistent(self, db):
        assert db.get_notification_template_by_id(9999) is None

    # --- update ---

    def test_update_name(self, db):
        tpl = db.create_notification_template(name="old_name", body="body")
        updated = db.update_notification_template(template_id=tpl.id, name="new_name")
        assert updated is not None
        assert updated.name == "new_name"
        assert updated.body == "body"

    def test_update_body(self, db):
        tpl = db.create_notification_template(name="tpl", body="old body")
        updated = db.update_notification_template(template_id=tpl.id, body="new body")
        assert updated is not None
        assert updated.body == "new body"
        assert updated.name == "tpl"

    def test_update_both_fields(self, db):
        tpl = db.create_notification_template(name="both", body="old")
        updated = db.update_notification_template(template_id=tpl.id, name="both_new", body="new")
        assert updated.name == "both_new"
        assert updated.body == "new"

    def test_update_nonexistent_returns_none(self, db):
        assert db.update_notification_template(template_id=9999, name="x") is None

    def test_update_duplicate_name_raises(self, db):
        db.create_notification_template(name="taken", body="b1")
        tpl2 = db.create_notification_template(name="other", body="b2")
        with pytest.raises(ValueError, match="已存在"):
            db.update_notification_template(template_id=tpl2.id, name="taken")

    def test_update_same_name_no_conflict(self, db):
        tpl = db.create_notification_template(name="same", body="old body")
        updated = db.update_notification_template(template_id=tpl.id, name="same", body="new body")
        assert updated is not None
        assert updated.body == "new body"

    def test_update_timestamps_change(self, db):
        tpl = db.create_notification_template(name="ts_test", body="body")
        original_updated_at = tpl.updated_at
        time.sleep(1)
        updated = db.update_notification_template(template_id=tpl.id, body="changed")
        assert updated.updated_at >= original_updated_at
        assert updated.created_at == tpl.created_at

    # --- delete ---

    def test_delete_existing(self, db):
        tpl = db.create_notification_template(name="to_delete", body="bye")
        result = db.delete_notification_template(tpl.id)
        assert result is True
        assert db.get_notification_template_by_id(tpl.id) is None

    def test_delete_nonexistent_returns_false(self, db):
        assert db.delete_notification_template(9999) is False

    def test_delete_reduces_list(self, db):
        t1 = db.create_notification_template(name="keep", body="a")
        t2 = db.create_notification_template(name="remove", body="b")
        db.delete_notification_template(t2.id)
        templates = db.get_notification_templates()
        assert len(templates) == 1
        assert templates[0].id == t1.id

    # --- placeholder content ---

    def test_body_with_placeholders(self, db):
        body = "Hello {{ username }}, your message: {{ message }}"
        tpl = db.create_notification_template(name="placeholder_test", body=body)
        fetched = db.get_notification_template_by_id(tpl.id)
        assert fetched.body == body

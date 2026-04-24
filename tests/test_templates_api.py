"""
Tests for the RESTful /api/templates/* endpoints.

Covers:
  - POST   /api/templates            → 201 + template object
  - GET    /api/templates            → 200 + array
  - GET    /api/templates/<id>       → 200 / 404
  - PUT    /api/templates/<id>       → 200 / 404 / 409
  - DELETE /api/templates/<id>       → 200 / 404
  - POST   /api/templates/<id>/preview → 200 / 404 / 400

Run with:
    python -m pytest tests/test_templates_api.py -v
"""

import os
import sys
import json
import re
import types
import asyncio
import pytest

# ---------------------------------------------------------------------------
# Bootstrap: inject minimal stubs for unavailable packages BEFORE any imports
# ---------------------------------------------------------------------------

def _build_stubs():
    """Inject quart + astrbot.core stubs so project modules can be imported."""
    # ── quart stub ──────────────────────────────────────────────────────────
    quart_mod = types.ModuleType("quart")

    class _Response:
        def __init__(self, data, status_code=200):
            if isinstance(data, (dict, list)):
                self._raw = json.dumps(data).encode()
            else:
                self._raw = data if isinstance(data, bytes) else str(data).encode()
            self.status_code = status_code

        @property
        def data(self):
            return self._raw

    quart_mod.jsonify = lambda d: _Response(d)
    quart_mod.request = types.SimpleNamespace(_json=None, args={})
    quart_mod.send_from_directory = lambda *a, **kw: _Response(b"")
    quart_mod.Quart = type("Quart", (), {})
    sys.modules["quart"] = quart_mod

    # ── astrbot package stubs ───────────────────────────────────────────────
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    astrbot_pkg = types.ModuleType("astrbot")
    astrbot_pkg.__path__ = [os.path.join(repo_root, "astrbot")]
    astrbot_pkg.__package__ = "astrbot"
    sys.modules.setdefault("astrbot", astrbot_pkg)

    core_pkg = types.ModuleType("astrbot.core")
    core_pkg.__path__ = [os.path.join(repo_root, "astrbot", "core")]
    core_pkg.__package__ = "astrbot.core"
    core_pkg.logger = types.SimpleNamespace(
        error=lambda *a, **k: None,
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
    )
    sys.modules.setdefault("astrbot.core", core_pkg)

    cfg_pkg = types.ModuleType("astrbot.core.config")
    cfg_pkg.__path__ = []
    sys.modules.setdefault("astrbot.core.config", cfg_pkg)

    cfg_sub = types.ModuleType("astrbot.core.config.astrbot_config")
    cfg_sub.AstrBotConfig = type("AstrBotConfig", (), {})
    sys.modules.setdefault("astrbot.core.config.astrbot_config", cfg_sub)


_build_stubs()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Safe to import project modules now
from astrbot.core.db.sqlite import SQLiteDatabase
import astrbot.dashboard.routes.templates_api as _api_mod
from astrbot.dashboard.routes.templates_api import register_template_routes


# ---------------------------------------------------------------------------
# Minimal async test harness (no Quart / pytest-asyncio required)
# ---------------------------------------------------------------------------

class _FakeApp:
    """Collect route registrations and dispatch calls synchronously."""

    def __init__(self):
        self._routes: dict = {}  # (path_pattern, METHOD) -> handler

    def route(self, path, methods=None):
        methods = [m.upper() for m in (methods or ["GET"])]

        def decorator(fn):
            for m in methods:
                self._routes[(path, m)] = fn
            return fn

        return decorator

    def _resolve(self, path: str, method: str):
        """Return (handler, kwargs) for the given path+method."""
        method = method.upper()
        # Exact match first
        if (path, method) in self._routes:
            return self._routes[(path, method)], {}
        # Pattern match: <int:x> and <x> segments
        for (pat, m), fn in self._routes.items():
            if m != method:
                continue
            # Extract param names in order
            param_names = re.findall(r"<(?:int:)?(\w+)>", pat)
            # Build a plain regex (no named groups to avoid Python 3.13 issues)
            regex = re.sub(r"<int:\w+>", r"([0-9]+)", pat)
            regex = re.sub(r"<\w+>", r"([^/]+)", regex)
            match = re.fullmatch(regex, path)
            if match:
                vals = match.groups()
                kwargs = {
                    name: int(val) if val.isdigit() else val
                    for name, val in zip(param_names, vals)
                }
                return fn, kwargs
        return None, {}


def _call(app: _FakeApp, path: str, method: str, json_data=None):
    """Invoke a registered route handler and return (status_code, data_dict)."""
    handler, kwargs = app._resolve(path, method)
    assert handler is not None, f"No handler registered for {method} {path}"

    # Patch the `request` name that was imported into templates_api
    orig_request = _api_mod.request
    fake_request = types.SimpleNamespace(_json=json_data, args={})

    async def _get_json():
        return json_data

    fake_request.get_json = _get_json
    _api_mod.request = fake_request

    try:
        result = asyncio.get_event_loop().run_until_complete(handler(**kwargs))
    finally:
        _api_mod.request = orig_request

    if isinstance(result, tuple):
        body, status = result
    else:
        body, status = result, 200

    data = json.loads(body.data)
    return status, data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    return SQLiteDatabase(str(tmp_path / "test.db"))


@pytest.fixture
def app(db):
    fake_app = _FakeApp()
    register_template_routes(fake_app, db)
    return fake_app


# ---------------------------------------------------------------------------
# POST /api/templates
# ---------------------------------------------------------------------------

class TestCreateTemplate:
    def test_create_returns_201(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "welcome", "body": "Hi {{ username }}!"})
        assert status == 201

    def test_create_returns_template_object(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "greet", "body": "Hello {{ name }}"})
        assert status == 201
        assert data["name"] == "greet"
        assert data["body"] == "Hello {{ name }}"
        assert data["id"] > 0
        assert "placeholders" in data
        assert data["placeholders"] == ["name"]
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_missing_name_returns_400(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"body": "Hello"})
        assert status == 400

    def test_create_missing_body_returns_400(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "test"})
        assert status == 400

    def test_create_empty_body_returns_400(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "test", "body": ""})
        assert status == 400

    def test_create_duplicate_name_returns_409(self, app):
        _call(app, "/api/templates", "POST", {"name": "dup", "body": "body1"})
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "dup", "body": "body2"})
        assert status == 409

    def test_create_invalid_syntax_returns_400(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "bad", "body": "Hi {{  }}!"})
        assert status == 400
        assert "syntax_errors" in data

    def test_create_with_filter_syntax(self, app):
        status, data = _call(app, "/api/templates", "POST",
                             {"name": "filtered", "body": "Hi {{ username|upper }}!"})
        assert status == 201
        assert data["placeholders"] == ["username"]

    def test_create_no_body_returns_400(self, app):
        status, data = _call(app, "/api/templates", "POST", None)
        assert status == 400


# ---------------------------------------------------------------------------
# GET /api/templates
# ---------------------------------------------------------------------------

class TestListTemplates:
    def test_list_returns_200(self, app):
        status, data = _call(app, "/api/templates", "GET")
        assert status == 200

    def test_list_returns_array(self, app):
        status, data = _call(app, "/api/templates", "GET")
        assert isinstance(data, list)

    def test_list_empty_initially(self, app):
        status, data = _call(app, "/api/templates", "GET")
        assert data == []

    def test_list_contains_created_templates(self, app):
        _call(app, "/api/templates", "POST", {"name": "t1", "body": "body1"})
        _call(app, "/api/templates", "POST", {"name": "t2", "body": "body2"})
        status, data = _call(app, "/api/templates", "GET")
        assert status == 200
        assert len(data) == 2
        names = [t["name"] for t in data]
        assert "t1" in names
        assert "t2" in names

    def test_list_items_have_required_fields(self, app):
        _call(app, "/api/templates", "POST", {"name": "check", "body": "{{ x }}"})
        status, data = _call(app, "/api/templates", "GET")
        item = data[0]
        for field in ("id", "name", "body", "placeholders", "created_at", "updated_at"):
            assert field in item, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/templates/<id>
# ---------------------------------------------------------------------------

class TestGetTemplate:
    def test_get_existing_returns_200(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "fetch_me", "body": "content"})
        status, data = _call(app, f"/api/templates/{created['id']}", "GET")
        assert status == 200
        assert data["id"] == created["id"]
        assert data["name"] == "fetch_me"

    def test_get_nonexistent_returns_404(self, app):
        status, data = _call(app, "/api/templates/9999", "GET")
        assert status == 404

    def test_get_returns_placeholders(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "ph_test", "body": "{{ a }} {{ b }}"})
        status, data = _call(app, f"/api/templates/{created['id']}", "GET")
        assert status == 200
        assert set(data["placeholders"]) == {"a", "b"}


# ---------------------------------------------------------------------------
# PUT /api/templates/<id>
# ---------------------------------------------------------------------------

class TestUpdateTemplate:
    def test_update_name_returns_200(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "old", "body": "body"})
        status, data = _call(app, f"/api/templates/{created['id']}", "PUT",
                             {"name": "new"})
        assert status == 200
        assert data["name"] == "new"
        assert data["body"] == "body"

    def test_update_body_returns_200(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "tpl", "body": "old body"})
        status, data = _call(app, f"/api/templates/{created['id']}", "PUT",
                             {"body": "new body"})
        assert status == 200
        assert data["body"] == "new body"

    def test_update_both_fields(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "both", "body": "old"})
        status, data = _call(app, f"/api/templates/{created['id']}", "PUT",
                             {"name": "both_new", "body": "new"})
        assert status == 200
        assert data["name"] == "both_new"
        assert data["body"] == "new"

    def test_update_nonexistent_returns_404(self, app):
        status, data = _call(app, "/api/templates/9999", "PUT", {"name": "x"})
        assert status == 404

    def test_update_duplicate_name_returns_409(self, app):
        _call(app, "/api/templates", "POST", {"name": "taken", "body": "b1"})
        _, tpl2 = _call(app, "/api/templates", "POST", {"name": "other", "body": "b2"})
        status, data = _call(app, f"/api/templates/{tpl2['id']}", "PUT",
                             {"name": "taken"})
        assert status == 409

    def test_update_invalid_syntax_returns_400(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "syn", "body": "valid {{ x }}"})
        status, data = _call(app, f"/api/templates/{created['id']}", "PUT",
                             {"body": "bad {{  }}"})
        assert status == 400

    def test_update_no_fields_returns_400(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "nf", "body": "body"})
        status, data = _call(app, f"/api/templates/{created['id']}", "PUT", {})
        assert status == 400

    def test_update_returns_updated_placeholders(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "ph", "body": "{{ a }}"})
        status, data = _call(app, f"/api/templates/{created['id']}", "PUT",
                             {"body": "{{ x }} {{ y }}"})
        assert status == 200
        assert set(data["placeholders"]) == {"x", "y"}


# ---------------------------------------------------------------------------
# DELETE /api/templates/<id>
# ---------------------------------------------------------------------------

class TestDeleteTemplate:
    def test_delete_existing_returns_200(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "to_del", "body": "bye"})
        status, data = _call(app, f"/api/templates/{created['id']}", "DELETE")
        assert status == 200

    def test_delete_removes_from_list(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "gone", "body": "bye"})
        _call(app, f"/api/templates/{created['id']}", "DELETE")
        status, data = _call(app, "/api/templates", "GET")
        ids = [t["id"] for t in data]
        assert created["id"] not in ids

    def test_delete_nonexistent_returns_404(self, app):
        status, data = _call(app, "/api/templates/9999", "DELETE")
        assert status == 404

    def test_delete_twice_returns_404(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "once", "body": "body"})
        _call(app, f"/api/templates/{created['id']}", "DELETE")
        status, _ = _call(app, f"/api/templates/{created['id']}", "DELETE")
        assert status == 404


# ---------------------------------------------------------------------------
# POST /api/templates/<id>/preview
# ---------------------------------------------------------------------------

class TestPreviewTemplate:
    def test_preview_returns_200(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "pv", "body": "Hi {{ name }}!"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {"name": "Alice"}})
        assert status == 200

    def test_preview_renders_correctly(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "render", "body": "Hello {{ name }}!"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {"name": "World"}})
        assert status == 200
        assert data["rendered"] == "Hello World!"
        assert data["warnings"] == []

    def test_preview_nonexistent_returns_404(self, app):
        status, data = _call(app, "/api/templates/9999/preview", "POST",
                             {"variables": {}})
        assert status == 404

    def test_preview_missing_var_keep(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "miss", "body": "Hi {{ name }}!"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {}, "missing_strategy": "keep"})
        assert status == 200
        assert "{{ name }}" in data["rendered"]
        assert len(data["warnings"]) == 1

    def test_preview_missing_var_empty(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "emp", "body": "Hi {{ name }}!"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {}, "missing_strategy": "empty"})
        assert status == 200
        assert data["rendered"] == "Hi !"

    def test_preview_with_filter_upper(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "filt", "body": "Hi {{ username|upper }}!"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {"username": "alice"}})
        assert status == 200
        assert data["rendered"] == "Hi ALICE!"

    def test_preview_with_filter_default(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "def_filt",
                            "body": 'Count: {{ count|default("0") }}'})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {}})
        assert status == 200
        assert data["rendered"] == "Count: 0"

    def test_preview_with_filter_lower(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "low", "body": "{{ msg|lower }}"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {"msg": "HELLO"}})
        assert status == 200
        assert data["rendered"] == "hello"

    def test_preview_with_filter_truncate(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "trunc", "body": "{{ text|truncate(5) }}"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {"text": "Hello World"}})
        assert status == 200
        assert data["rendered"] == "Hello…"

    def test_preview_returns_placeholders(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "phs", "body": "{{ a }} {{ b }}"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {"a": "1", "b": "2"}})
        assert status == 200
        assert set(data["placeholders"]) == {"a", "b"}

    def test_preview_no_variables_defaults_to_keep(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "novars", "body": "Hi {{ x }}!"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {})
        assert status == 200
        assert "{{ x }}" in data["rendered"]

    def test_preview_invalid_strategy_returns_400(self, app):
        _, created = _call(app, "/api/templates", "POST",
                           {"name": "strat", "body": "{{ x }}"})
        status, data = _call(app, f"/api/templates/{created['id']}/preview", "POST",
                             {"variables": {}, "missing_strategy": "invalid"})
        assert status == 400

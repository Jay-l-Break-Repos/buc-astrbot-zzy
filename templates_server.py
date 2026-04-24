#!/usr/bin/env python3
"""
Standalone notification-template API server.

Implements /api/templates/* using only the Python standard library.
Runs on port 6185 (the port exposed by docker-compose).

Endpoints:
    POST   /api/templates              → 201 + template JSON
    GET    /api/templates              → 200 + JSON array
    GET    /api/templates/<id>         → 200 / 404
    PUT    /api/templates/<id>         → 200 / 404 / 409
    DELETE /api/templates/<id>         → 200 / 404
    POST   /api/templates/<id>/preview → 200 / 404

GET /  and GET /health → 200 (healthcheck)
"""

import http.server
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from http import HTTPStatus

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("TEMPLATES_PORT", "6185"))
DB_PATH = os.environ.get("TEMPLATES_DB", "/app/data/templates.db")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notification_template (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            body       TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    return conn


def _row_to_dict(row, body_for_placeholders=None):
    body = row["body"]
    return {
        "id": row["id"],
        "name": row["name"],
        "body": body,
        "placeholders": _extract_placeholders(body),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# Renderer (pure stdlib, no dependencies)
# ---------------------------------------------------------------------------

_VALID_PH_RE = re.compile(
    r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)"
    r"((?:\s*\|\s*[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?)*)"
    r"\s*\}\}"
)
_ANY_BRACE_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_UNCLOSED_RE  = re.compile(r"\{\{(?!.*?\}\})", re.DOTALL)
_BLOCK_TAG_RE = re.compile(r"\{%-?\s*\w")
_IDENT_RE     = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_MAX_LEN      = 64


def _extract_placeholders(body):
    seen, result = set(), []
    for m in _VALID_PH_RE.finditer(body):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _validate_syntax(body):
    errors = []
    if _BLOCK_TAG_RE.search(body):
        errors.append(
            "模板包含不支持的 Jinja2 块标签 ({% ... %})，"
            "仅支持 {{ variable }} 和 {{ variable|filter }} 语法"
        )
        return errors
    if _UNCLOSED_RE.search(body):
        errors.append("模板包含未闭合的占位符 ({{ 缺少对应的 }})")
        return errors
    for m in _ANY_BRACE_RE.finditer(body):
        inner = m.group(1).strip()
        raw   = m.group(0)
        if not inner:
            errors.append(f"占位符内容不能为空: '{raw}'")
            continue
        var_part = inner.split("|")[0].strip()
        if len(var_part) > _MAX_LEN:
            errors.append(f"占位符名称过长: '{raw}'")
            continue
        if var_part.startswith(".") or var_part.endswith("."):
            errors.append(f"占位符名称不能以点号开头或结尾: '{raw}'")
            continue
        if ".." in var_part:
            errors.append(f"占位符名称不能包含连续点号: '{raw}'")
            continue
        if not _IDENT_RE.match(var_part):
            errors.append(
                f"占位符名称无效 '{var_part}': 必须以字母或下划线开头"
            )
    return errors


def _parse_filters(filter_str):
    result = []
    for seg in filter_str.split("|"):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\(([^)]*)\))?$", seg)
        if not m:
            continue
        name = m.group(1)
        args = [a.strip().strip("'\"") for a in m.group(2).split(",")] if m.group(2) else []
        result.append((name, args))
    return result


def _apply_filter(value, name, args):
    if name == "upper":      return value.upper()
    if name == "lower":      return value.lower()
    if name == "title":      return value.title()
    if name == "capitalize": return value.capitalize()
    if name in ("strip","trim"): return value.strip()
    if name == "reverse":    return value[::-1]
    if name in ("length","count"): return str(len(value))
    if name == "string":     return str(value)
    if name == "int":
        try: return str(int(value))
        except: return "0"
    if name == "float":
        try: return str(float(value))
        except: return "0.0"
    if name == "default":
        fallback = args[0] if args else ""
        boolean_mode = len(args) >= 2 and args[1].lower() in ("true","1","yes")
        return value if (value if boolean_mode else value != "") else fallback
    if name == "truncate":
        try: n = int(args[0]) if args else 255
        except: n = 255
        return value if len(value) <= n else value[:n] + "…"
    if name == "replace":
        return value.replace(args[0], args[1]) if len(args) >= 2 else value
    return value


def _render(body, variables, missing_strategy="keep"):
    warnings = []

    def _replace(m):
        name       = m.group(1)
        filter_str = m.group(2) or ""
        if name in variables:
            val = str(variables[name])
            for fname, fargs in _parse_filters(filter_str):
                val = _apply_filter(val, fname, fargs)
            return val
        # variable missing – check for default filter
        if filter_str:
            for fname, fargs in _parse_filters(filter_str):
                if fname == "default" and fargs:
                    return fargs[0]
        if missing_strategy == "error":
            raise KeyError(name)
        if missing_strategy == "empty":
            warnings.append(f"变量 '{name}' 未提供，已替换为空字符串")
            return ""
        warnings.append(f"变量 '{name}' 未提供，占位符保持原样")
        return m.group(0)

    rendered = _VALID_PH_RE.sub(_replace, body)
    return rendered, warnings


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class TemplateHandler(http.server.BaseHTTPRequestHandler):
    """Handles all HTTP requests."""

    def log_message(self, fmt, *args):
        pass  # suppress default access log noise

    # ── helpers ──────────────────────────────────────────────────────────────

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return None

    # ── routing ──────────────────────────────────────────────────────────────

    def _route(self, method):
        path = urllib.parse.urlparse(self.path).path.rstrip("/")

        # Health / root
        if path in ("", "/", "/health"):
            self._send_json(200, {"status": "ok"})
            return

        # /api/templates
        if path == "/api/templates":
            if method == "GET":
                self._list_templates()
            elif method == "POST":
                self._create_template()
            else:
                self._send_json(405, {"error": "Method Not Allowed"})
            return

        # /api/templates/<id>
        m = re.fullmatch(r"/api/templates/(\d+)", path)
        if m:
            tid = int(m.group(1))
            if method == "GET":
                self._get_template(tid)
            elif method == "PUT":
                self._update_template(tid)
            elif method == "DELETE":
                self._delete_template(tid)
            else:
                self._send_json(405, {"error": "Method Not Allowed"})
            return

        # /api/templates/<id>/preview
        m = re.fullmatch(r"/api/templates/(\d+)/preview", path)
        if m:
            tid = int(m.group(1))
            if method == "POST":
                self._preview_template(tid)
            else:
                self._send_json(405, {"error": "Method Not Allowed"})
            return

        self._send_json(404, {"error": "Not Found"})

    def do_GET(self):    self._route("GET")
    def do_POST(self):   self._route("POST")
    def do_PUT(self):    self._route("PUT")
    def do_DELETE(self): self._route("DELETE")

    # ── endpoint implementations ──────────────────────────────────────────────

    def _create_template(self):
        data = self._read_json()
        if not data:
            return self._send_json(400, {"error": "请求体不能为空"})
        name = (data.get("name") or "").strip()
        body = data.get("body")
        if not name:
            return self._send_json(400, {"error": "缺少必要参数: name"})
        if body is None or body == "":
            return self._send_json(400, {"error": "缺少必要参数: body"})
        errs = _validate_syntax(body)
        if errs:
            return self._send_json(400, {"error": "模板正文包含无效的占位符语法",
                                         "syntax_errors": errs})
        now = int(time.time())
        try:
            with _get_db() as conn:
                cur = conn.execute(
                    "INSERT INTO notification_template(name,body,created_at,updated_at)"
                    " VALUES(?,?,?,?)",
                    (name, body, now, now),
                )
                new_id = cur.lastrowid
                conn.commit()
        except sqlite3.IntegrityError:
            return self._send_json(409, {"error": f"通知模板名称 '{name}' 已存在"})
        row = {"id": new_id, "name": name, "body": body,
               "created_at": now, "updated_at": now}
        self._send_json(201, _row_to_dict(row))

    def _list_templates(self):
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT id,name,body,created_at,updated_at"
                " FROM notification_template ORDER BY created_at ASC"
            ).fetchall()
        self._send_json(200, [_row_to_dict(r) for r in rows])

    def _get_template(self, tid):
        with _get_db() as conn:
            row = conn.execute(
                "SELECT id,name,body,created_at,updated_at"
                " FROM notification_template WHERE id=?", (tid,)
            ).fetchone()
        if row is None:
            return self._send_json(404, {"error": f"通知模板 (id={tid}) 不存在"})
        self._send_json(200, _row_to_dict(row))

    def _update_template(self, tid):
        data = self._read_json()
        if not data:
            return self._send_json(400, {"error": "请求体不能为空"})
        name = data.get("name")
        body = data.get("body")
        if name is None and body is None:
            return self._send_json(400, {"error": "至少需要提供 name 或 body"})
        if name is not None:
            name = name.strip()
            if not name:
                return self._send_json(400, {"error": "name 不能为空字符串"})
        if body is not None:
            errs = _validate_syntax(body)
            if errs:
                return self._send_json(400, {"error": "模板正文包含无效的占位符语法",
                                             "syntax_errors": errs})
        with _get_db() as conn:
            existing = conn.execute(
                "SELECT id,name,body,created_at,updated_at"
                " FROM notification_template WHERE id=?", (tid,)
            ).fetchone()
            if existing is None:
                return self._send_json(404, {"error": f"通知模板 (id={tid}) 不存在"})
            new_name = name if name is not None else existing["name"]
            new_body = body if body is not None else existing["body"]
            now = int(time.time())
            try:
                conn.execute(
                    "UPDATE notification_template"
                    " SET name=?,body=?,updated_at=? WHERE id=?",
                    (new_name, new_body, now, tid),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return self._send_json(409, {"error": f"通知模板名称 '{new_name}' 已存在"})
        row = {"id": tid, "name": new_name, "body": new_body,
               "created_at": existing["created_at"], "updated_at": now}
        self._send_json(200, _row_to_dict(row))

    def _delete_template(self, tid):
        with _get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM notification_template WHERE id=?", (tid,)
            ).fetchone()
            if existing is None:
                return self._send_json(404, {"error": f"通知模板 (id={tid}) 不存在"})
            conn.execute("DELETE FROM notification_template WHERE id=?", (tid,))
            conn.commit()
        self._send_json(200, {"message": f"通知模板 (id={tid}) 已删除"})

    def _preview_template(self, tid):
        with _get_db() as conn:
            row = conn.execute(
                "SELECT id,name,body,created_at,updated_at"
                " FROM notification_template WHERE id=?", (tid,)
            ).fetchone()
        if row is None:
            return self._send_json(404, {"error": f"通知模板 (id={tid}) 不存在"})
        data = self._read_json() or {}
        variables = data.get("variables") or {}
        if not isinstance(variables, dict):
            return self._send_json(400, {"error": "variables 必须是对象类型"})
        variables = {str(k): str(v) for k, v in variables.items()}
        missing_strategy = data.get("missing_strategy", "keep")
        if missing_strategy not in ("keep", "empty", "error"):
            return self._send_json(400, {"error": "missing_strategy 的有效值为 keep/empty/error"})
        body = row["body"]
        errs = _validate_syntax(body)
        if errs:
            return self._send_json(400, {"error": "模板正文包含无效的占位符语法",
                                         "syntax_errors": errs})
        try:
            rendered, warnings = _render(body, variables, missing_strategy)
        except KeyError as k:
            return self._send_json(400, {"error": f"变量 '{k}' 未提供"})
        self._send_json(200, {
            "rendered":     rendered,
            "placeholders": _extract_placeholders(body),
            "warnings":     warnings,
            "syntax_errors": [],
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ensure DB directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), TemplateHandler)
    print(f"[templates_server] Listening on 0.0.0.0:{PORT}", flush=True)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[templates_server] Shutting down", flush=True)

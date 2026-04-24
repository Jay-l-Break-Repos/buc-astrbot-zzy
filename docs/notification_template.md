# Notification Template System — Step 1: Data Model & CRUD API

This document describes the foundation of the custom notification template system
introduced in Step 1.

---

## Overview

The notification template system lets users define reusable message templates with
named variable placeholders (e.g. `{{ username }}`, `{{ message }}`). In Step 1 we
establish the core data model and the full CRUD API so templates can be persisted,
retrieved, updated, and deleted.

---

## Data Model

### `NotificationTemplate` (`astrbot/core/db/po.py`)

| Field        | Type  | Description                                      |
|--------------|-------|--------------------------------------------------|
| `id`         | `int` | Auto-increment primary key                       |
| `name`       | `str` | Unique human-readable identifier for the template |
| `body`       | `str` | Template content; may contain `{{ var }}` tokens |
| `created_at` | `int` | Unix timestamp of creation                       |
| `updated_at` | `int` | Unix timestamp of last modification              |

### Database Table (`sqlite_init.sql`)

```sql
CREATE TABLE IF NOT EXISTS notification_template(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    body       TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
```

---

## API Endpoints

All endpoints are registered under the `/api` prefix by `NotificationTemplateRoute`.

### `POST /api/notification_template/create`

Create a new template.

**Request body (JSON):**
```json
{
  "name": "welcome",
  "body": "Hello {{ username }}, welcome to {{ platform }}!"
}
```

**Success response:**
```json
{
  "status": "ok",
  "data": {
    "id": 1,
    "name": "welcome",
    "body": "Hello {{ username }}, welcome to {{ platform }}!",
    "created_at": 1714000000,
    "updated_at": 1714000000
  }
}
```

**Error response (duplicate name):**
```json
{ "status": "error", "message": "通知模板名称 'welcome' 已存在" }
```

---

### `GET /api/notification_template/list`

Return all templates ordered by `created_at` ascending.

**Success response:**
```json
{
  "status": "ok",
  "data": {
    "templates": [
      { "id": 1, "name": "welcome", "body": "...", "created_at": ..., "updated_at": ... },
      { "id": 2, "name": "alert",   "body": "...", "created_at": ..., "updated_at": ... }
    ]
  }
}
```

---

### `GET /api/notification_template/detail?id=<id>`

Fetch a single template by its primary key.

**Query parameter:** `id` (integer)

**Success response:**
```json
{
  "status": "ok",
  "data": { "id": 1, "name": "welcome", "body": "...", "created_at": ..., "updated_at": ... }
}
```

**Error response (not found):**
```json
{ "status": "error", "message": "通知模板 (id=99) 不存在" }
```

---

### `POST /api/notification_template/update`

Update an existing template's `name` and/or `body`. At least one field must be supplied.

**Request body (JSON):**
```json
{
  "id": 1,
  "name": "welcome_v2",
  "body": "Hi {{ username }}!"
}
```

**Success response:** updated template object (same shape as create).

**Error responses:**
- `id` not found → `{ "status": "error", "message": "通知模板 (id=1) 不存在" }`
- name conflict → `{ "status": "error", "message": "通知模板名称 'welcome_v2' 已存在" }`

---

### `POST /api/notification_template/delete`

Delete a template by ID.

**Request body (JSON):**
```json
{ "id": 1 }
```

**Success response:**
```json
{ "status": "ok", "data": { "message": "通知模板 (id=1) 已删除" } }
```

**Error response (not found):**
```json
{ "status": "error", "message": "通知模板 (id=1) 不存在" }
```

---

## File Structure

```
astrbot/
├── core/
│   └── db/
│       ├── __init__.py          # BaseDatabase abstract class (CRUD abstract methods)
│       ├── po.py                # NotificationTemplate dataclass
│       ├── sqlite.py            # SQLiteDatabase concrete CRUD implementation
│       └── sqlite_init.sql      # Schema (notification_template table)
└── dashboard/
    └── routes/
        ├── __init__.py          # Exports NotificationTemplateRoute
        ├── notification_template.py  # Quart async route handlers
        └── route.py             # Base Route / RouteContext / Response helpers

tests/
└── test_notification_template.py   # 20 pytest tests (all passing)
```

---

## Running Tests

```bash
python -m pytest tests/test_notification_template.py -v
```

Expected output: **20 passed**.

---

## What's Next (Step 2)

- Variable placeholder extraction from `body` (regex scan for `{{ var }}` tokens)
- Template preview endpoint — render a template with supplied variable values

# Notification Template System — Step 2: Placeholder Parsing & Template Preview

This document describes the placeholder parsing, validation, and preview
functionality added in Step 2, building on the data model and CRUD API from Step 1.

---

## Overview

Step 2 adds three capabilities on top of the Step 1 foundation:

1. **Placeholder extraction** — parse a template body and return the list of
   `{{ variable_name }}` tokens it contains.
2. **Syntax validation** — detect malformed placeholder syntax (empty names,
   invalid identifiers, unclosed braces, stray closing braces) and return a
   clear error message.
3. **Template preview** — render a template with caller-supplied variable values
   and report which variables are still unresolved.

---

## New Module: `astrbot/core/template/placeholder.py`

A pure-Python utility module with **no** database or web-framework dependencies.

### `extract_placeholders(body: str) -> List[str]`

Return an ordered, deduplicated list of variable names found in *body*.

```python
from astrbot.core.template.placeholder import extract_placeholders

extract_placeholders("Hello {{ username }}, welcome to {{ platform }}!")
# → ['username', 'platform']

extract_placeholders("{{ a }} and {{ a }} again")
# → ['a']   (deduplicated, order preserved)

extract_placeholders("No placeholders here.")
# → []
```

**Rules:**
- Only well-formed `{{ identifier }}` tokens are returned.
- Identifier must match `[A-Za-z_]\w*` (letters, digits, underscores; cannot start with a digit).
- Surrounding whitespace inside `{{ … }}` is ignored.
- Malformed tokens are silently skipped (use `validate_body` for strict checking).

---

### `validate_body(body: str) -> None`

Raise `ValueError` with a descriptive Chinese-language message if *body* contains
any malformed placeholder syntax.

```python
from astrbot.core.template.placeholder import validate_body

validate_body("Hello {{ username }}!")   # OK — no exception

validate_body("{{ }}")                   # ValueError: 变量名不能为空
validate_body("{{ 123abc }}")            # ValueError: 无效的变量名 '123abc'
validate_body("{{ foo bar }}")           # ValueError: 无效的变量名 'foo bar'
validate_body("Hello {{ unclosed")       # ValueError: 未闭合的 '{{'
validate_body("stray }} close")          # ValueError: 多余的 '}}'
```

**Detected errors:**

| Condition | Example | Error keyword |
|-----------|---------|---------------|
| Unclosed `{{` | `{{ name` | `未闭合` |
| Stray `}}` | `hello }}` | `多余的` |
| Empty identifier | `{{ }}` | `变量名不能为空` |
| Invalid identifier | `{{ 123 }}`, `{{ foo bar }}` | `无效的变量名` |

---

### `render_template(body: str, variables: dict) -> str`

Replace every `{{ var }}` token in *body* with the corresponding value from
*variables*. Unknown placeholders are left unchanged.

```python
from astrbot.core.template.placeholder import render_template

render_template("Hello {{ name }}!", {"name": "Alice"})
# → "Hello Alice!"

render_template("{{ a }} + {{ b }}", {"a": "1"})
# → "1 + {{ b }}"   ({{ b }} left unchanged — not in variables)
```

---

## New API Endpoints

### `GET /api/notification_template/placeholders?id=<id>`

Extract and return the placeholder variable names from a stored template.

**Query parameter:** `id` (integer)

**Success response:**
```json
{
  "status": "ok",
  "data": {
    "template_id": 1,
    "placeholders": ["username", "platform"]
  }
}
```

**Error response (not found):**
```json
{ "status": "error", "message": "通知模板 (id=99) 不存在" }
```

---

### `POST /api/notification_template/preview`

Render a template with the supplied variable values.

**Request body (JSON):**
```json
{
  "id": 1,
  "variables": {
    "username": "Alice",
    "platform": "AstrBot"
  }
}
```

`variables` is optional and defaults to `{}`.

**Success response:**
```json
{
  "status": "ok",
  "data": {
    "template_id": 1,
    "rendered":     "Hello Alice, welcome to AstrBot!",
    "placeholders": ["username", "platform"],
    "missing":      []
  }
}
```

**Response with missing variables:**
```json
{
  "status": "ok",
  "data": {
    "template_id": 1,
    "rendered":     "Hello Alice, welcome to {{ platform }}!",
    "placeholders": ["username", "platform"],
    "missing":      ["platform"]
  }
}
```

**Error response (syntax error in stored template):**
```json
{ "status": "error", "message": "模板语法错误：占位符 '{{ }}' 的变量名不能为空" }
```

**Error response (invalid `variables` type):**
```json
{ "status": "error", "message": "variables 必须是一个 JSON 对象（键值对）" }
```

---

## Validation in Create / Update

The `create` and `update` endpoints now validate the template body for placeholder
syntax **before** persisting to the database.  If the body is malformed, a
`400`-style error response is returned immediately.

---

## File Structure (updated)

```
astrbot/
├── core/
│   ├── db/
│   │   ├── __init__.py          # BaseDatabase abstract class
│   │   ├── po.py                # NotificationTemplate dataclass
│   │   ├── sqlite.py            # SQLiteDatabase CRUD implementation
│   │   └── sqlite_init.sql      # Schema
│   └── template/
│       ├── __init__.py          # Package marker
│       └── placeholder.py       # extract_placeholders / validate_body / render_template
└── dashboard/
    └── routes/
        ├── __init__.py
        ├── notification_template.py  # CRUD + placeholders + preview endpoints
        └── route.py

tests/
├── test_notification_template.py    # 20 CRUD tests (Step 1)
└── test_template_placeholder.py     # 56 placeholder/preview tests (Step 2)
```

---

## Running Tests

```bash
# Step 1 tests (CRUD)
python -m pytest tests/test_notification_template.py -v

# Step 2 tests (placeholder parsing + preview)
python -m pytest tests/test_template_placeholder.py -v

# All tests together
python -m pytest tests/ -v
```

Expected: **76 passed** (20 Step 1 + 56 Step 2).

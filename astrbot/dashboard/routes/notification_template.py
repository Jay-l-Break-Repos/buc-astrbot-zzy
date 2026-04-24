"""Dashboard API routes for Notification Template CRUD operations.

Endpoints (all prefixed with /api by register_routes()):
    POST   /api/notification_template/create          – create a new template
    GET    /api/notification_template/list            – list all templates
    GET    /api/notification_template/detail          – get one template (?id=<id>)
    POST   /api/notification_template/update          – update an existing template
    POST   /api/notification_template/delete          – delete a template
    POST   /api/notification_template/preview         – render a template with sample data
    GET    /api/notification_template/extract         – extract placeholders from a body
"""

import traceback
from .route import Route, Response, RouteContext
from astrbot.core import logger
from quart import request
from astrbot.core.db import BaseDatabase
from astrbot.core.notification_template.engine import (
    extract_placeholders,
    render_template,
    TemplateSyntaxError,
)


class NotificationTemplateRoute(Route):
    """Handles CRUD + preview API endpoints for notification message templates."""

    def __init__(self, context: RouteContext, db_helper: BaseDatabase) -> None:
        super().__init__(context)
        self.db_helper = db_helper
        self.routes = {
            "/notification_template/create":  ("POST", self.create_template),
            "/notification_template/list":    ("GET",  self.list_templates),
            "/notification_template/detail":  ("GET",  self.get_template),
            "/notification_template/update":  ("POST", self.update_template),
            "/notification_template/delete":  ("POST", self.delete_template),
            "/notification_template/preview": ("POST", self.preview_template),
            "/notification_template/extract": ("GET",  self.extract_template_placeholders),
        }
        self.register_routes()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _template_to_dict(tpl) -> dict:
        """Serialize a NotificationTemplate dataclass to a plain dict."""
        return {
            "id":         tpl.id,
            "name":       tpl.name,
            "body":       tpl.body,
            "created_at": tpl.created_at,
            "updated_at": tpl.updated_at,
        }

    @staticmethod
    def _validate_body(body: str) -> list:
        """Validate *body* and return its placeholder list.

        Raises ``TemplateSyntaxError`` (a subclass of ``ValueError``) on
        invalid placeholder syntax so callers can surface a clean error.
        """
        return extract_placeholders(body)

    # ------------------------------------------------------------------
    # POST /api/notification_template/create
    # ------------------------------------------------------------------

    async def create_template(self):
        """Create a new notification template.

        Request body (JSON)::

            {
                "name": "<unique template name>",
                "body": "<template body with {{ placeholders }}>"
            }

        Response::

            {
                "status": "ok",
                "data": {
                    "id": <int>,
                    "name": "<name>",
                    "body": "<body>",
                    "placeholders": ["var1", "var2", ...],
                    "created_at": <unix_ts>,
                    "updated_at": <unix_ts>
                }
            }

        Error codes:
            - 400 (status=error): missing/empty fields or invalid placeholder syntax
            - 409 (status=error): duplicate template name
        """
        try:
            data = await request.get_json()
            if not data:
                return Response().error("请求体不能为空").__dict__

            name = (data.get("name") or "").strip()
            body = data.get("body")

            if not name:
                return Response().error("缺少必要参数: name").__dict__
            if body is None or body == "":
                return Response().error("缺少必要参数: body").__dict__

            # ── validate placeholder syntax before touching the DB ──────────
            try:
                placeholders = self._validate_body(body)
            except TemplateSyntaxError as e:
                return Response().error(str(e)).__dict__

            template = self.db_helper.create_notification_template(name=name, body=body)
            result = self._template_to_dict(template)
            result["placeholders"] = placeholders
            return Response().ok(result).__dict__

        except ValueError as e:
            # Duplicate name from DB layer
            return Response().error(str(e)).__dict__
        except Exception as e:
            logger.error(f"创建通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"创建通知模板失败: {e}").__dict__

    # ------------------------------------------------------------------
    # GET /api/notification_template/list
    # ------------------------------------------------------------------

    async def list_templates(self):
        """Return all notification templates ordered by creation time (ascending).

        Response::

            {
                "status": "ok",
                "data": {
                    "templates": [
                        { "id": ..., "name": ..., "body": ...,
                          "placeholders": [...],
                          "created_at": ..., "updated_at": ... },
                        ...
                    ]
                }
            }
        """
        try:
            templates = self.db_helper.get_notification_templates()
            items = []
            for t in templates:
                d = self._template_to_dict(t)
                try:
                    d["placeholders"] = extract_placeholders(t.body)
                except TemplateSyntaxError:
                    # Stored template has legacy/invalid syntax — return empty list
                    d["placeholders"] = []
                items.append(d)
            return Response().ok({"templates": items}).__dict__
        except Exception as e:
            logger.error(f"获取通知模板列表失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"获取通知模板列表失败: {e}").__dict__

    # ------------------------------------------------------------------
    # GET /api/notification_template/detail?id=<id>
    # ------------------------------------------------------------------

    async def get_template(self):
        """Fetch a single notification template by its ID.

        Query parameter:
            id (int): the template primary key

        Response::

            {
                "status": "ok",
                "data": {
                    "id": ..., "name": ..., "body": ...,
                    "placeholders": [...],
                    "created_at": ..., "updated_at": ...
                }
            }
        """
        try:
            template_id = request.args.get("id", type=int)
            if template_id is None:
                return Response().error("缺少必要参数: id").__dict__

            template = self.db_helper.get_notification_template_by_id(template_id)
            if template is None:
                return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__

            result = self._template_to_dict(template)
            try:
                result["placeholders"] = extract_placeholders(template.body)
            except TemplateSyntaxError:
                result["placeholders"] = []
            return Response().ok(result).__dict__
        except Exception as e:
            logger.error(f"获取通知模板详情失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"获取通知模板详情失败: {e}").__dict__

    # ------------------------------------------------------------------
    # POST /api/notification_template/update
    # ------------------------------------------------------------------

    async def update_template(self):
        """Update an existing notification template's name and/or body.

        Request body (JSON)::

            {
                "id":   <int>,           // required
                "name": "<new name>",    // optional
                "body": "<new body>"     // optional
            }

        At least one of ``name`` or ``body`` must be provided alongside ``id``.

        Response::

            {
                "status": "ok",
                "data": {
                    "id": ..., "name": ..., "body": ...,
                    "placeholders": [...],
                    "created_at": ..., "updated_at": ...
                }
            }
        """
        try:
            data = await request.get_json()
            if not data:
                return Response().error("请求体不能为空").__dict__

            template_id = data.get("id")
            if template_id is None:
                return Response().error("缺少必要参数: id").__dict__

            name = data.get("name")
            body = data.get("body")

            if name is None and body is None:
                return Response().error("至少需要提供 name 或 body 中的一个字段").__dict__

            if name is not None:
                name = name.strip()
                if not name:
                    return Response().error("name 不能为空字符串").__dict__

            # ── validate new body syntax before touching the DB ─────────────
            if body is not None:
                try:
                    placeholders = self._validate_body(body)
                except TemplateSyntaxError as e:
                    return Response().error(str(e)).__dict__
            else:
                placeholders = None  # will be computed from stored body below

            updated = self.db_helper.update_notification_template(
                template_id=int(template_id), name=name, body=body
            )
            if updated is None:
                return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__

            result = self._template_to_dict(updated)
            if placeholders is None:
                try:
                    placeholders = extract_placeholders(updated.body)
                except TemplateSyntaxError:
                    placeholders = []
            result["placeholders"] = placeholders
            return Response().ok(result).__dict__

        except ValueError as e:
            return Response().error(str(e)).__dict__
        except Exception as e:
            logger.error(f"更新通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"更新通知模板失败: {e}").__dict__

    # ------------------------------------------------------------------
    # POST /api/notification_template/delete
    # ------------------------------------------------------------------

    async def delete_template(self):
        """Delete a notification template by ID.

        Request body (JSON)::

            { "id": <int> }

        Response::

            { "status": "ok", "data": { "message": "..." } }
        """
        try:
            data = await request.get_json()
            if not data:
                return Response().error("请求体不能为空").__dict__

            template_id = data.get("id")
            if template_id is None:
                return Response().error("缺少必要参数: id").__dict__

            deleted = self.db_helper.delete_notification_template(int(template_id))
            if not deleted:
                return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__

            return Response().ok({"message": f"通知模板 (id={template_id}) 已删除"}).__dict__

        except Exception as e:
            logger.error(f"删除通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"删除通知模板失败: {e}").__dict__

    # ------------------------------------------------------------------
    # POST /api/notification_template/preview
    # ------------------------------------------------------------------

    async def preview_template(self):
        """Render a template body with sample variable values.

        Accepts either an inline ``body`` string *or* a stored template
        ``id`` (the stored body is used in that case).

        Request body (JSON)::

            {
                // Provide exactly one of:
                "body": "<template body>",   // inline body
                "id":   <int>,               // use stored template body

                // Variable substitution values (all optional):
                "variables": {
                    "username": "Alice",
                    "message":  "Hello!"
                }
            }

        Response::

            {
                "status": "ok",
                "data": {
                    "rendered":      "<rendered text>",
                    "placeholders":  ["username", "message"],
                    "missing":       ["var_not_supplied"],
                    "extra":         ["supplied_but_not_in_template"]
                }
            }

        Error codes:
            - 400 (status=error): missing body/id, invalid placeholder syntax,
              or template ID not found
        """
        try:
            data = await request.get_json()
            if not data:
                return Response().error("请求体不能为空").__dict__

            body = data.get("body")
            template_id = data.get("id")
            variables = data.get("variables") or {}

            # ── resolve body ────────────────────────────────────────────────
            if body is None and template_id is None:
                return Response().error("请提供 body 或 id 中的一个").__dict__

            if body is None:
                # Load from DB
                tpl = self.db_helper.get_notification_template_by_id(int(template_id))
                if tpl is None:
                    return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__
                body = tpl.body

            if not isinstance(variables, dict):
                return Response().error("variables 必须是一个 JSON 对象").__dict__

            # ── validate & extract placeholders ─────────────────────────────
            try:
                placeholders = extract_placeholders(body)
            except TemplateSyntaxError as e:
                return Response().error(str(e)).__dict__

            # ── render ──────────────────────────────────────────────────────
            rendered = render_template(body, variables)

            # ── compute missing / extra keys for developer feedback ─────────
            placeholder_set = set(placeholders)
            variable_set    = set(variables.keys())
            missing = [p for p in placeholders if p not in variable_set]
            extra   = sorted(variable_set - placeholder_set)

            return Response().ok({
                "rendered":     rendered,
                "placeholders": placeholders,
                "missing":      missing,
                "extra":        extra,
            }).__dict__

        except Exception as e:
            logger.error(f"预览通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"预览通知模板失败: {e}").__dict__

    # ------------------------------------------------------------------
    # GET /api/notification_template/extract?body=<encoded_body>
    # ------------------------------------------------------------------

    async def extract_template_placeholders(self):
        """Extract placeholder names from a template body without saving.

        Query parameter:
            body (str): URL-encoded template body string

        Response::

            {
                "status": "ok",
                "data": {
                    "placeholders": ["username", "message", ...]
                }
            }

        Error codes:
            - 400 (status=error): missing body or invalid placeholder syntax
        """
        try:
            body = request.args.get("body")
            if body is None:
                return Response().error("缺少必要参数: body").__dict__

            try:
                placeholders = extract_placeholders(body)
            except TemplateSyntaxError as e:
                return Response().error(str(e)).__dict__

            return Response().ok({"placeholders": placeholders}).__dict__

        except Exception as e:
            logger.error(f"提取占位符失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"提取占位符失败: {e}").__dict__

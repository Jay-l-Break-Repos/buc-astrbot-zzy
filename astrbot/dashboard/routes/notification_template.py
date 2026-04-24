"""Dashboard API routes for Notification Template CRUD + rendering operations.

Endpoints (all prefixed with /api by register_routes()):
    POST   /api/notification_template/create   – create a new template
    GET    /api/notification_template/list     – list all templates
    GET    /api/notification_template/detail   – get one template (?id=<id>)
    POST   /api/notification_template/update   – update an existing template
    POST   /api/notification_template/delete   – delete a template
    POST   /api/notification_template/preview  – render a preview with sample data
"""

import traceback
from .route import Route, Response, RouteContext
from astrbot.core import logger
from quart import request
from astrbot.core.db import BaseDatabase
from astrbot.core.notification_template import (
    extract_placeholders,
    validate_placeholder_syntax,
    render_template,
)


class NotificationTemplateRoute(Route):
    """Handles CRUD + rendering API endpoints for notification message templates."""

    def __init__(self, context: RouteContext, db_helper: BaseDatabase) -> None:
        super().__init__(context)
        self.db_helper = db_helper
        self.routes = {
            "/notification_template/create": ("POST", self.create_template),
            "/notification_template/list": ("GET", self.list_templates),
            "/notification_template/detail": ("GET", self.get_template),
            "/notification_template/update": ("POST", self.update_template),
            "/notification_template/delete": ("POST", self.delete_template),
            "/notification_template/preview": ("POST", self.preview_template),
        }
        self.register_routes()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _template_to_dict(tpl) -> dict:
        """Serialize a NotificationTemplate dataclass to a plain dict.

        The serialized form also includes a ``placeholders`` list so callers
        can discover available variables without a separate request.
        """
        return {
            "id": tpl.id,
            "name": tpl.name,
            "body": tpl.body,
            "placeholders": extract_placeholders(tpl.body),
            "created_at": tpl.created_at,
            "updated_at": tpl.updated_at,
        }

    @staticmethod
    def _validate_body(body: str) -> list:
        """Return a list of syntax-error strings for *body*, or [] if valid."""
        return validate_placeholder_syntax(body)

    # ------------------------------------------------------------------
    # POST /api/notification_template/create
    # ------------------------------------------------------------------

    async def create_template(self):
        """Create a new notification template.

        Request body (JSON):
            {
                "name": "<unique template name>",
                "body": "<template body with {{ placeholders }}>"
            }

        Response (success):
            { "status": "ok", "data": { <template fields + placeholders> } }

        Response (validation error):
            { "status": "error", "message": "...", "data": { "syntax_errors": [...] } }
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

            # Validate placeholder syntax before persisting
            syntax_errors = self._validate_body(body)
            if syntax_errors:
                resp = Response()
                resp.status = "error"
                resp.message = "模板正文包含无效的占位符语法"
                resp.data = {"syntax_errors": syntax_errors}
                return resp.__dict__

            template = self.db_helper.create_notification_template(name=name, body=body)
            return Response().ok(self._template_to_dict(template)).__dict__

        except ValueError as e:
            # Duplicate name
            return Response().error(str(e)).__dict__
        except Exception as e:
            logger.error(f"创建通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"创建通知模板失败: {e}").__dict__

    # ------------------------------------------------------------------
    # GET /api/notification_template/list
    # ------------------------------------------------------------------

    async def list_templates(self):
        """Return all notification templates ordered by creation time (ascending).

        Response:
            { "status": "ok", "data": { "templates": [ ... ] } }
        """
        try:
            templates = self.db_helper.get_notification_templates()
            return Response().ok(
                {"templates": [self._template_to_dict(t) for t in templates]}
            ).__dict__
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

        Response:
            { "status": "ok", "data": { <template fields + placeholders> } }
        """
        try:
            template_id = request.args.get("id", type=int)
            if template_id is None:
                return Response().error("缺少必要参数: id").__dict__

            template = self.db_helper.get_notification_template_by_id(template_id)
            if template is None:
                return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__

            return Response().ok(self._template_to_dict(template)).__dict__
        except Exception as e:
            logger.error(f"获取通知模板详情失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"获取通知模板详情失败: {e}").__dict__

    # ------------------------------------------------------------------
    # POST /api/notification_template/update
    # ------------------------------------------------------------------

    async def update_template(self):
        """Update an existing notification template's name and/or body.

        Request body (JSON):
            {
                "id":   <int>,           // required
                "name": "<new name>",    // optional
                "body": "<new body>"     // optional
            }

        At least one of ``name`` or ``body`` must be provided alongside ``id``.

        Response (success):
            { "status": "ok", "data": { <updated template fields + placeholders> } }

        Response (validation error):
            { "status": "error", "message": "...", "data": { "syntax_errors": [...] } }
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

            # Validate placeholder syntax in the new body (if provided)
            if body is not None:
                syntax_errors = self._validate_body(body)
                if syntax_errors:
                    resp = Response()
                    resp.status = "error"
                    resp.message = "模板正文包含无效的占位符语法"
                    resp.data = {"syntax_errors": syntax_errors}
                    return resp.__dict__

            updated = self.db_helper.update_notification_template(
                template_id=int(template_id), name=name, body=body
            )
            if updated is None:
                return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__

            return Response().ok(self._template_to_dict(updated)).__dict__

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

        Request body (JSON):
            { "id": <int> }

        Response:
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
        """Render a template preview by substituting sample variable values.

        Accepts either an inline ``body`` string or an existing template ``id``.
        When both are supplied, ``body`` takes precedence.

        Request body (JSON):
            {
                // Provide one of:
                "body": "<template body>",   // inline body (takes precedence)
                "id":   <int>,               // OR load body from DB by id

                // Optional:
                "variables": {               // sample values for placeholders
                    "username": "Alice",
                    "count": "3"
                },
                "missing_strategy": "keep"   // "keep" | "empty" | "error"
                                             // default: "keep"
            }

        Response (success):
            {
                "status": "ok",
                "data": {
                    "rendered":      "<rendered text>",
                    "placeholders":  ["username", "count"],   // all found in body
                    "warnings":      [],                      // missing-var notices
                    "syntax_errors": []                       // always [] on success
                }
            }

        Response (syntax error):
            {
                "status": "error",
                "message": "模板正文包含无效的占位符语法",
                "data": { "syntax_errors": ["..."] }
            }
        """
        try:
            data = await request.get_json()
            if not data:
                return Response().error("请求体不能为空").__dict__

            # Resolve body ------------------------------------------------
            body = data.get("body")
            if body is None:
                template_id = data.get("id")
                if template_id is None:
                    return Response().error("必须提供 body 或 id 中的一个").__dict__
                template = self.db_helper.get_notification_template_by_id(int(template_id))
                if template is None:
                    return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__
                body = template.body

            if not isinstance(body, str):
                return Response().error("body 必须是字符串类型").__dict__

            # Validate syntax first ----------------------------------------
            syntax_errors = self._validate_body(body)
            if syntax_errors:
                resp = Response()
                resp.status = "error"
                resp.message = "模板正文包含无效的占位符语法"
                resp.data = {"syntax_errors": syntax_errors}
                return resp.__dict__

            # Resolve variables and strategy --------------------------------
            variables = data.get("variables") or {}
            if not isinstance(variables, dict):
                return Response().error("variables 必须是对象类型").__dict__

            # Coerce all values to str
            variables = {str(k): str(v) for k, v in variables.items()}

            missing_strategy = data.get("missing_strategy", "keep")
            if missing_strategy not in ("keep", "empty", "error"):
                return Response().error(
                    "missing_strategy 的有效值为 'keep'、'empty'、'error'"
                ).__dict__

            # Render --------------------------------------------------------
            try:
                rendered, warnings = render_template(
                    body, variables, missing_strategy=missing_strategy
                )
            except KeyError as missing_key:
                return Response().error(
                    f"变量 '{missing_key}' 未提供（missing_strategy='error'）"
                ).__dict__

            placeholders = extract_placeholders(body)

            return Response().ok(
                {
                    "rendered": rendered,
                    "placeholders": placeholders,
                    "warnings": warnings,
                    "syntax_errors": [],
                }
            ).__dict__

        except Exception as e:
            logger.error(f"预览通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"预览通知模板失败: {e}").__dict__

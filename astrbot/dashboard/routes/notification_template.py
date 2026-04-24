"""Dashboard API routes for Notification Template CRUD operations.

Endpoints (all prefixed with /api by register_routes()):
    POST   /api/notification_template/create      – create a new template
    GET    /api/notification_template/list        – list all templates
    GET    /api/notification_template/detail      – get one template (?id=<id>)
    POST   /api/notification_template/update      – update an existing template
    POST   /api/notification_template/delete      – delete a template
    GET    /api/notification_template/placeholders – extract placeholder names (?id=<id>)
    POST   /api/notification_template/preview     – render a template with variable values
"""

import traceback
from .route import Route, Response, RouteContext
from astrbot.core import logger
from quart import request
from astrbot.core.db import BaseDatabase
from astrbot.core.template.placeholder import (
    extract_placeholders,
    validate_body,
    render_template,
)


class NotificationTemplateRoute(Route):
    """Handles CRUD + preview API endpoints for notification message templates."""

    def __init__(self, context: RouteContext, db_helper: BaseDatabase) -> None:
        super().__init__(context)
        self.db_helper = db_helper
        self.routes = {
            "/notification_template/create":       ("POST", self.create_template),
            "/notification_template/list":         ("GET",  self.list_templates),
            "/notification_template/detail":       ("GET",  self.get_template),
            "/notification_template/update":       ("POST", self.update_template),
            "/notification_template/delete":       ("POST", self.delete_template),
            "/notification_template/placeholders": ("GET",  self.get_placeholders),
            "/notification_template/preview":      ("POST", self.preview_template),
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

        The body is validated for placeholder syntax before persisting.

        Response:
            { "status": "ok", "data": { <template fields> } }
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
            try:
                validate_body(body)
            except ValueError as ve:
                return Response().error(str(ve)).__dict__

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
            { "status": "ok", "data": { <template fields> } }
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
        If ``body`` is provided it is validated for placeholder syntax.

        Response:
            { "status": "ok", "data": { <updated template fields> } }
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

            # Validate placeholder syntax if body is being updated
            if body is not None:
                try:
                    validate_body(body)
                except ValueError as ve:
                    return Response().error(str(ve)).__dict__

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
    # GET /api/notification_template/placeholders?id=<id>
    # ------------------------------------------------------------------

    async def get_placeholders(self):
        """Extract and return the placeholder variable names from a template.

        Query parameter:
            id (int): the template primary key

        Response:
            {
                "status": "ok",
                "data": {
                    "template_id": <int>,
                    "placeholders": ["var1", "var2", ...]
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

            placeholders = extract_placeholders(template.body)
            return Response().ok({
                "template_id":  template_id,
                "placeholders": placeholders,
            }).__dict__

        except Exception as e:
            logger.error(f"提取占位符失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"提取占位符失败: {e}").__dict__

    # ------------------------------------------------------------------
    # POST /api/notification_template/preview
    # ------------------------------------------------------------------

    async def preview_template(self):
        """Render a template with the supplied variable values and return the result.

        Request body (JSON):
            {
                "id":        <int>,                  // required — template to preview
                "variables": { "var1": "val1", ... } // optional — defaults to {}
            }

        The template body is validated for placeholder syntax before rendering.
        Any placeholder whose name is not present in *variables* is left
        unchanged in the output so the caller can see which variables are still
        unresolved.

        Response (success):
            {
                "status": "ok",
                "data": {
                    "template_id":    <int>,
                    "rendered":       "<rendered string>",
                    "placeholders":   ["var1", "var2", ...],  // all vars in template
                    "missing":        ["var2", ...]           // vars not supplied
                }
            }

        Response (error — template not found):
            { "status": "error", "message": "通知模板 (id=X) 不存在" }

        Response (error — invalid syntax):
            { "status": "error", "message": "模板语法错误：..." }
        """
        try:
            data = await request.get_json()
            if not data:
                return Response().error("请求体不能为空").__dict__

            template_id = data.get("id")
            if template_id is None:
                return Response().error("缺少必要参数: id").__dict__

            variables = data.get("variables") or {}
            if not isinstance(variables, dict):
                return Response().error("variables 必须是一个 JSON 对象（键值对）").__dict__

            template = self.db_helper.get_notification_template_by_id(int(template_id))
            if template is None:
                return Response().error(f"通知模板 (id={template_id}) 不存在").__dict__

            # Validate syntax before rendering
            try:
                validate_body(template.body)
            except ValueError as ve:
                return Response().error(str(ve)).__dict__

            all_placeholders = extract_placeholders(template.body)
            missing = [p for p in all_placeholders if p not in variables]
            rendered = render_template(template.body, variables)

            return Response().ok({
                "template_id":  int(template_id),
                "rendered":     rendered,
                "placeholders": all_placeholders,
                "missing":      missing,
            }).__dict__

        except Exception as e:
            logger.error(f"预览通知模板失败: {e}\n{traceback.format_exc()}")
            return Response().error(f"预览通知模板失败: {e}").__dict__

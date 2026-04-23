"""Dashboard API routes for Notification Template CRUD operations.

Endpoints (all prefixed with /api):
    POST   /templates              – create a new template (201)
    GET    /templates              – list all templates (returns array)
    GET    /templates/<id>         – get a single template by id
    PUT    /templates/<id>         – update an existing template
    DELETE /templates/<id>         – delete a template
    POST   /templates/<id>/preview – render template with provided variables
"""

import traceback
from .route import Route, Response, RouteContext
from astrbot.core import logger
from quart import request, jsonify
from astrbot.core.db import BaseDatabase

try:
    from jinja2 import Environment, TemplateSyntaxError, StrictUndefined
    _JINJA2_AVAILABLE = True
except ImportError:
    _JINJA2_AVAILABLE = False


def _validate_jinja2(body: str) -> str | None:
    """Validate Jinja2 template syntax.

    Returns an error message string if the template is invalid,
    or None if it is valid.
    """
    if not _JINJA2_AVAILABLE:
        return None  # Can't validate without jinja2; skip
    try:
        env = Environment()
        env.parse(body)
        return None
    except TemplateSyntaxError as exc:
        return f"模板语法错误 (行 {exc.lineno}): {exc.message}"


def _render_jinja2(body: str, variables: dict) -> str:
    """Render a Jinja2 template with the given variables.

    Raises TemplateSyntaxError or UndefinedError on failure.
    """
    env = Environment(undefined=StrictUndefined)
    tmpl = env.from_string(body)
    return tmpl.render(**variables)


class NotificationTemplateRoute(Route):
    """Handles CRUD API endpoints for notification message templates."""

    def __init__(self, context: RouteContext, db_helper: BaseDatabase) -> None:
        super().__init__(context)
        self.db_helper = db_helper
        # Register routes manually to support path parameters and multiple
        # HTTP methods on the same path.
        self.app.add_url_rule(
            "/api/templates",
            view_func=self.templates_collection,
            methods=["GET", "POST"],
        )
        self.app.add_url_rule(
            "/api/templates/<int:template_id>",
            view_func=self.templates_item,
            methods=["GET", "PUT", "DELETE"],
        )
        self.app.add_url_rule(
            "/api/templates/<int:template_id>/preview",
            view_func=self.templates_preview,
            methods=["POST"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _template_to_dict(tpl) -> dict:
        """Serialize a NotificationTemplate dataclass to a plain dict."""
        return {
            "id": tpl.id,
            "name": tpl.name,
            "body": tpl.body,
            "created_at": tpl.created_at,
            "updated_at": tpl.updated_at,
        }

    @staticmethod
    def _json_response(data, status_code: int = 200):
        """Return a Quart JSON response with the given status code."""
        resp = jsonify(data)
        resp.status_code = status_code
        return resp

    # ------------------------------------------------------------------
    # Collection endpoint: GET /api/templates  &  POST /api/templates
    # ------------------------------------------------------------------

    async def templates_collection(self):
        if request.method == "GET":
            return await self._list_templates()
        return await self._create_template()

    async def _create_template(self):
        """POST /api/templates

        Request body (JSON):
            {
                "name": "<unique template name>",
                "body": "<template body with {{ placeholders }}>"
            }

        Response (201):
            { "id": ..., "name": ..., "body": ..., "created_at": ..., "updated_at": ... }
        """
        try:
            data = await request.get_json()
            if not data:
                return self._json_response({"error": "请求体不能为空"}, 400)

            name = (data.get("name") or "").strip()
            body = data.get("body")

            if not name:
                return self._json_response({"error": "缺少必要参数: name"}, 400)
            if body is None or body == "":
                return self._json_response({"error": "缺少必要参数: body"}, 400)

            # Validate Jinja2 syntax
            syntax_error = _validate_jinja2(body)
            if syntax_error:
                return self._json_response({"error": syntax_error}, 400)

            template = self.db_helper.create_notification_template(name=name, body=body)
            return self._json_response(self._template_to_dict(template), 201)

        except ValueError as e:
            # Duplicate name
            return self._json_response({"error": str(e)}, 409)
        except Exception as e:
            logger.error(f"创建通知模板失败: {e}\n{traceback.format_exc()}")
            return self._json_response({"error": f"创建通知模板失败: {e}"}, 500)

    async def _list_templates(self):
        """GET /api/templates

        Returns all templates ordered by creation time (ascending).

        Response (200):
            [ { "id": ..., "name": ..., "body": ..., ... }, ... ]
        """
        try:
            templates = self.db_helper.get_notification_templates()
            return self._json_response(
                [self._template_to_dict(t) for t in templates], 200
            )
        except Exception as e:
            logger.error(f"获取通知模板列表失败: {e}\n{traceback.format_exc()}")
            return self._json_response({"error": f"获取通知模板列表失败: {e}"}, 500)

    # ------------------------------------------------------------------
    # Item endpoint: GET/PUT/DELETE /api/templates/<id>
    # ------------------------------------------------------------------

    async def templates_item(self, template_id: int):
        if request.method == "GET":
            return await self._get_template(template_id)
        if request.method == "PUT":
            return await self._update_template(template_id)
        return await self._delete_template(template_id)

    async def _get_template(self, template_id: int):
        """GET /api/templates/<id>

        Response (200):
            { "id": ..., "name": ..., "body": ..., "created_at": ..., "updated_at": ... }
        """
        try:
            template = self.db_helper.get_notification_template_by_id(template_id)
            if template is None:
                return self._json_response(
                    {"error": f"通知模板 (id={template_id}) 不存在"}, 404
                )
            return self._json_response(self._template_to_dict(template), 200)
        except Exception as e:
            logger.error(f"获取通知模板详情失败: {e}\n{traceback.format_exc()}")
            return self._json_response({"error": f"获取通知模板详情失败: {e}"}, 500)

    async def _update_template(self, template_id: int):
        """PUT /api/templates/<id>

        Request body (JSON):
            {
                "name": "<new name>",   // optional
                "body": "<new body>"    // optional
            }

        At least one of ``name`` or ``body`` must be provided.

        Response (200):
            { "id": ..., "name": ..., "body": ..., "created_at": ..., "updated_at": ... }
        """
        try:
            data = await request.get_json()
            if not data:
                return self._json_response({"error": "请求体不能为空"}, 400)

            name = data.get("name")
            body = data.get("body")

            if name is None and body is None:
                return self._json_response(
                    {"error": "至少需要提供 name 或 body 中的一个字段"}, 400
                )

            # Normalise name
            if name is not None:
                name = name.strip()
                if not name:
                    return self._json_response({"error": "name 不能为空字符串"}, 400)

            # Validate Jinja2 syntax if body is being updated
            if body is not None:
                syntax_error = _validate_jinja2(body)
                if syntax_error:
                    return self._json_response({"error": syntax_error}, 400)

            updated = self.db_helper.update_notification_template(
                template_id=template_id, name=name, body=body
            )
            if updated is None:
                return self._json_response(
                    {"error": f"通知模板 (id={template_id}) 不存在"}, 404
                )
            return self._json_response(self._template_to_dict(updated), 200)

        except ValueError as e:
            return self._json_response({"error": str(e)}, 409)
        except Exception as e:
            logger.error(f"更新通知模板失败: {e}\n{traceback.format_exc()}")
            return self._json_response({"error": f"更新通知模板失败: {e}"}, 500)

    async def _delete_template(self, template_id: int):
        """DELETE /api/templates/<id>

        Response (200):
            { "message": "通知模板 (id=<id>) 已删除" }
        """
        try:
            deleted = self.db_helper.delete_notification_template(template_id)
            if not deleted:
                return self._json_response(
                    {"error": f"通知模板 (id={template_id}) 不存在"}, 404
                )
            return self._json_response(
                {"message": f"通知模板 (id={template_id}) 已删除"}, 200
            )
        except Exception as e:
            logger.error(f"删除通知模板失败: {e}\n{traceback.format_exc()}")
            return self._json_response({"error": f"删除通知模板失败: {e}"}, 500)

    # ------------------------------------------------------------------
    # Preview endpoint: POST /api/templates/<id>/preview
    # ------------------------------------------------------------------

    async def templates_preview(self, template_id: int):
        """POST /api/templates/<id>/preview

        Render the template body with the provided variables using Jinja2.

        Request body (JSON):
            { "variables": { "username": "Alice", ... } }

        Response (200):
            { "rendered": "<rendered text>" }
        """
        try:
            template = self.db_helper.get_notification_template_by_id(template_id)
            if template is None:
                return self._json_response(
                    {"error": f"通知模板 (id={template_id}) 不存在"}, 404
                )

            data = await request.get_json()
            variables = {}
            if data:
                variables = data.get("variables", {})
            if not isinstance(variables, dict):
                return self._json_response(
                    {"error": "variables 必须是一个对象"}, 400
                )

            if not _JINJA2_AVAILABLE:
                return self._json_response(
                    {"error": "服务器未安装 Jinja2，无法渲染模板"}, 500
                )

            try:
                rendered = _render_jinja2(template.body, variables)
            except Exception as render_err:
                return self._json_response(
                    {"error": f"模板渲染失败: {render_err}"}, 400
                )

            return self._json_response({"rendered": rendered}, 200)

        except Exception as e:
            logger.error(f"预览通知模板失败: {e}\n{traceback.format_exc()}")
            return self._json_response({"error": f"预览通知模板失败: {e}"}, 500)

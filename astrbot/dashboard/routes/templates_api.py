"""RESTful API routes for Notification Template CRUD + rendering.

Endpoints (registered directly on the Quart app, no /api prefix from Route):
    POST   /api/templates            – create a new template        (201)
    GET    /api/templates            – list all templates            (200)
    GET    /api/templates/<id>       – get one template              (200/404)
    PUT    /api/templates/<id>       – update a template             (200/404)
    DELETE /api/templates/<id>       – delete a template             (200/404)
    POST   /api/templates/<id>/preview – render preview              (200/404)
"""

import traceback
from quart import request, jsonify
from astrbot.core.db import BaseDatabase
from astrbot.core.notification_template import (
    extract_placeholders,
    validate_placeholder_syntax,
    render_template,
)

try:
    from astrbot.core import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)


def _template_to_dict(tpl) -> dict:
    """Serialize a NotificationTemplate dataclass to a plain dict."""
    return {
        "id": tpl.id,
        "name": tpl.name,
        "body": tpl.body,
        "placeholders": extract_placeholders(tpl.body),
        "created_at": tpl.created_at,
        "updated_at": tpl.updated_at,
    }


def register_template_routes(app, db_helper: BaseDatabase):
    """Register all /api/templates/* routes on *app*.

    Args:
        app:       The Quart application instance.
        db_helper: A :class:`BaseDatabase` implementation used for persistence.
    """

    # ------------------------------------------------------------------
    # POST /api/templates  →  201 + template object
    # ------------------------------------------------------------------
    @app.route("/api/templates", methods=["POST"])
    async def create_template():
        try:
            data = await request.get_json()
            if not data:
                return jsonify({"error": "请求体不能为空"}), 400

            name = (data.get("name") or "").strip()
            body = data.get("body")

            if not name:
                return jsonify({"error": "缺少必要参数: name"}), 400
            if body is None or body == "":
                return jsonify({"error": "缺少必要参数: body"}), 400

            syntax_errors = validate_placeholder_syntax(body)
            if syntax_errors:
                return jsonify({"error": "模板正文包含无效的占位符语法",
                                "syntax_errors": syntax_errors}), 400

            template = db_helper.create_notification_template(name=name, body=body)
            return jsonify(_template_to_dict(template)), 201

        except ValueError as e:
            return jsonify({"error": str(e)}), 409
        except Exception as e:
            logger.error(f"创建通知模板失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"创建通知模板失败: {e}"}), 500

    # ------------------------------------------------------------------
    # GET /api/templates  →  200 + array of templates
    # ------------------------------------------------------------------
    @app.route("/api/templates", methods=["GET"])
    async def list_templates():
        try:
            templates = db_helper.get_notification_templates()
            return jsonify([_template_to_dict(t) for t in templates]), 200
        except Exception as e:
            logger.error(f"获取通知模板列表失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"获取通知模板列表失败: {e}"}), 500

    # ------------------------------------------------------------------
    # GET /api/templates/<id>  →  200 + template object  |  404
    # ------------------------------------------------------------------
    @app.route("/api/templates/<int:template_id>", methods=["GET"])
    async def get_template(template_id: int):
        try:
            template = db_helper.get_notification_template_by_id(template_id)
            if template is None:
                return jsonify({"error": f"通知模板 (id={template_id}) 不存在"}), 404
            return jsonify(_template_to_dict(template)), 200
        except Exception as e:
            logger.error(f"获取通知模板详情失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"获取通知模板详情失败: {e}"}), 500

    # ------------------------------------------------------------------
    # PUT /api/templates/<id>  →  200 + updated template  |  404
    # ------------------------------------------------------------------
    @app.route("/api/templates/<int:template_id>", methods=["PUT"])
    async def update_template(template_id: int):
        try:
            data = await request.get_json()
            if not data:
                return jsonify({"error": "请求体不能为空"}), 400

            name = data.get("name")
            body = data.get("body")

            if name is None and body is None:
                return jsonify({"error": "至少需要提供 name 或 body 中的一个字段"}), 400

            if name is not None:
                name = name.strip()
                if not name:
                    return jsonify({"error": "name 不能为空字符串"}), 400

            if body is not None:
                syntax_errors = validate_placeholder_syntax(body)
                if syntax_errors:
                    return jsonify({"error": "模板正文包含无效的占位符语法",
                                    "syntax_errors": syntax_errors}), 400

            updated = db_helper.update_notification_template(
                template_id=template_id, name=name, body=body
            )
            if updated is None:
                return jsonify({"error": f"通知模板 (id={template_id}) 不存在"}), 404

            return jsonify(_template_to_dict(updated)), 200

        except ValueError as e:
            return jsonify({"error": str(e)}), 409
        except Exception as e:
            logger.error(f"更新通知模板失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"更新通知模板失败: {e}"}), 500

    # ------------------------------------------------------------------
    # DELETE /api/templates/<id>  →  200  |  404
    # ------------------------------------------------------------------
    @app.route("/api/templates/<int:template_id>", methods=["DELETE"])
    async def delete_template(template_id: int):
        try:
            deleted = db_helper.delete_notification_template(template_id)
            if not deleted:
                return jsonify({"error": f"通知模板 (id={template_id}) 不存在"}), 404
            return jsonify({"message": f"通知模板 (id={template_id}) 已删除"}), 200
        except Exception as e:
            logger.error(f"删除通知模板失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"删除通知模板失败: {e}"}), 500

    # ------------------------------------------------------------------
    # POST /api/templates/<id>/preview  →  200  |  404
    # ------------------------------------------------------------------
    @app.route("/api/templates/<int:template_id>/preview", methods=["POST"])
    async def preview_template(template_id: int):
        try:
            template = db_helper.get_notification_template_by_id(template_id)
            if template is None:
                return jsonify({"error": f"通知模板 (id={template_id}) 不存在"}), 404

            data = await request.get_json() or {}
            variables = data.get("variables") or {}
            if not isinstance(variables, dict):
                return jsonify({"error": "variables 必须是对象类型"}), 400

            variables = {str(k): str(v) for k, v in variables.items()}

            missing_strategy = data.get("missing_strategy", "keep")
            if missing_strategy not in ("keep", "empty", "error"):
                return jsonify({"error": "missing_strategy 的有效值为 'keep'、'empty'、'error'"}), 400

            syntax_errors = validate_placeholder_syntax(template.body)
            if syntax_errors:
                return jsonify({"error": "模板正文包含无效的占位符语法",
                                "syntax_errors": syntax_errors}), 400

            try:
                rendered, warnings = render_template(
                    template.body, variables, missing_strategy=missing_strategy
                )
            except KeyError as missing_key:
                return jsonify({"error": f"变量 '{missing_key}' 未提供（missing_strategy='error'）"}), 400

            return jsonify({
                "rendered": rendered,
                "placeholders": extract_placeholders(template.body),
                "warnings": warnings,
                "syntax_errors": [],
            }), 200

        except Exception as e:
            logger.error(f"预览通知模板失败: {e}\n{traceback.format_exc()}")
            return jsonify({"error": f"预览通知模板失败: {e}"}), 500

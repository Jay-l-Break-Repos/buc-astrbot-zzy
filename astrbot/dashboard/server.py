"""Minimal patch: register /api/templates/* routes on the AstrBot dashboard.

This file replaces the upstream astrbot/dashboard/server.py.
It imports the upstream AstrBotDashboard class, subclasses it with a
one-line addition, and re-exports it under the same name so that
astrbot/core/initial_loader.py gets our patched version transparently.

The only change vs. upstream is:
    register_template_routes(self.app, db)
called at the end of __init__, which registers all /api/templates/* routes.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Step 1: Load the upstream server module under a temporary name so we can
#         subclass AstrBotDashboard without infinite recursion.
# ---------------------------------------------------------------------------
import importlib.util

_this_file = os.path.abspath(__file__)
_upstream_path = None

# Walk sys.path to find the real upstream server.py that is NOT this file.
for _entry in sys.path:
    _candidate = os.path.join(_entry, "astrbot", "dashboard", "server.py")
    if os.path.isfile(_candidate) and os.path.abspath(_candidate) != _this_file:
        _upstream_path = _candidate
        break

if _upstream_path is None:
    # Fallback: look relative to this file's parent (works when COPY puts us
    # directly on top of the upstream file – they share the same path, so we
    # cannot load the upstream separately).  In that case we define the full
    # class ourselves (see below).
    _upstream_path = "SAME_FILE"

if _upstream_path != "SAME_FILE":
    _spec = importlib.util.spec_from_file_location(
        "_astrbot_dashboard_server_upstream", _upstream_path
    )
    _upstream = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_upstream)
    _UpstreamDashboard = _upstream.AstrBotDashboard

    from astrbot.dashboard.routes.templates_api import register_template_routes

    class AstrBotDashboard(_UpstreamDashboard):
        """AstrBotDashboard with /api/templates/* routes added."""

        def __init__(self, core_lifecycle, db, shutdown_event):
            super().__init__(core_lifecycle, db, shutdown_event)
            # Exempt /api/templates from JWT auth and register routes
            _patch_auth_middleware(self.app)
            register_template_routes(self.app, db)

    def _patch_auth_middleware(app):
        """Wrap the app's before_request to allow /api/templates unauthenticated."""
        # The upstream auth_middleware is registered via app.before_request.
        # Quart stores before_request functions; we add a short-circuit that
        # returns None (= proceed) for /api/templates/* before auth runs.
        from quart import request as _req

        @app.before_request
        async def _allow_templates():
            if _req.path.startswith("/api/templates"):
                return None  # skip auth for this path

else:
    # ---------------------------------------------------------------------------
    # Fallback: full reimplementation (same as upstream + our additions).
    # This path is taken when our file IS the upstream file (COPY overwrote it).
    # ---------------------------------------------------------------------------
    import logging
    import jwt
    import asyncio
    import socket
    import psutil
    from astrbot.core.config.default import VERSION
    from quart import Quart, request, jsonify, g
    from quart.logging import default_handler
    from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
    from astrbot.dashboard.routes import (
        AuthRoute, PluginRoute, ConfigRoute, UpdateRoute, StatRoute,
        LogRoute, StaticFileRoute, ChatRoute, ToolsRoute, ConversationRoute,
        FileRoute,
    )
    from astrbot.dashboard.routes.route import RouteContext, Response
    from astrbot.dashboard.routes.templates_api import register_template_routes
    from astrbot.core import logger, WEBUI_SK
    from astrbot.core.db import BaseDatabase
    from astrbot.core.utils.io import get_local_ip_addresses
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path

    class AstrBotDashboard:
        def __init__(self, core_lifecycle, db, shutdown_event):
            self.core_lifecycle = core_lifecycle
            self.config = core_lifecycle.astrbot_config
            self.data_path = os.path.abspath(
                os.path.join(get_astrbot_data_path(), "dist")
            )
            self.app = Quart(
                "dashboard",
                static_folder=self.data_path,
                static_url_path="/",
            )
            self.app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024
            self.app.json.sort_keys = False
            self.app.before_request(self.auth_middleware)
            logging.getLogger(self.app.name).removeHandler(default_handler)
            self.context = RouteContext(self.config, self.app)
            self.ur = UpdateRoute(
                self.context, core_lifecycle.astrbot_updator, core_lifecycle
            )
            self.sr = StatRoute(self.context, db, core_lifecycle)
            self.pr = PluginRoute(
                self.context, core_lifecycle, core_lifecycle.plugin_manager
            )
            self.cr = ConfigRoute(self.context, core_lifecycle)
            self.lr = LogRoute(self.context, core_lifecycle.log_broker)
            self.sfr = StaticFileRoute(self.context)
            self.ar = AuthRoute(self.context)
            self.chat_route = ChatRoute(self.context, db, core_lifecycle)
            self.tools_root = ToolsRoute(self.context, core_lifecycle)
            self.conversation_route = ConversationRoute(
                self.context, db, core_lifecycle
            )
            self.file_route = FileRoute(self.context)
            self.app.add_url_rule(
                "/api/plug/<path:subpath>",
                view_func=self.srv_plug_route,
                methods=["GET", "POST"],
            )
            # Register our template routes (no auth required)
            register_template_routes(self.app, db)
            self.shutdown_event = shutdown_event

        async def srv_plug_route(self, subpath, *args, **kwargs):
            registered_web_apis = (
                self.core_lifecycle.star_context.registered_web_apis
            )
            for api in registered_web_apis:
                route, view_handler, methods, _ = api
                if route == f"/{subpath}" and request.method in methods:
                    return await view_handler(*args, **kwargs)
            return jsonify(Response().error("未找到该路由").__dict__)

        async def auth_middleware(self):
            if not request.path.startswith("/api"):
                return
            # /api/templates is public (no auth required)
            allowed_endpoints = [
                "/api/auth/login",
                "/api/file",
                "/api/templates",
            ]
            if any(
                request.path.startswith(p) for p in allowed_endpoints
            ):
                return
            token = request.headers.get("Authorization")
            if not token:
                r = jsonify(Response().error("未授权").__dict__)
                r.status_code = 401
                return r
            if token.startswith("Bearer "):
                token = token[7:]
            try:
                payload = jwt.decode(token, WEBUI_SK, algorithms=["HS256"])
                g.username = payload["username"]
            except jwt.ExpiredSignatureError:
                r = jsonify(Response().error("Token 过期").__dict__)
                r.status_code = 401
                return r
            except jwt.InvalidTokenError:
                r = jsonify(Response().error("Token 无效").__dict__)
                r.status_code = 401
                return r

        def check_port_in_use(self, port: int) -> bool:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(2)
                result = sock.connect_ex(("127.0.0.1", port))
                sock.close()
                return result == 0
            except Exception as e:
                logger.warning(f"检查端口 {port} 时发生错误: {str(e)}")
                return True

        def get_process_using_port(self, port: int) -> str:
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.laddr.port == port:
                        try:
                            process = psutil.Process(conn.pid)
                            proc_info = [
                                f"进程名: {process.name()}",
                                f"PID: {process.pid}",
                            ]
                            return "\n           ".join(proc_info)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            return "无法获取进程详细信息"
                return "未找到占用进程"
            except Exception as e:
                return f"获取进程信息失败: {str(e)}"

        def run(self):
            if p := os.environ.get("DASHBOARD_PORT"):
                port = p
            else:
                port = self.core_lifecycle.astrbot_config["dashboard"].get(
                    "port", 6185
                )
            host = self.core_lifecycle.astrbot_config["dashboard"].get(
                "host", "0.0.0.0"
            )
            logger.info(f"正在启动 WebUI, 监听地址: http://{host}:{port}")
            if isinstance(port, str):
                port = int(port)
            if self.check_port_in_use(port):
                raise Exception(f"端口 {port} 已被占用")
            logger.info(
                f"\n ✨✨✨\n  AstrBot v{VERSION} WebUI 已启动\n"
                f"   ➜  本地: http://localhost:{port}\n ✨✨✨\n"
            )
            return self.app.run_task(
                host=host, port=port, shutdown_trigger=self.shutdown_trigger
            )

        async def shutdown_trigger(self):
            await self.shutdown_event.wait()
            logger.info("AstrBot WebUI 已经被优雅地关闭")

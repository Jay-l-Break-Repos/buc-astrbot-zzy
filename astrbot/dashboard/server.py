"""Minimal AstrBot dashboard server overlay.

Loads the upstream AstrBotDashboard, subclasses it to add
/api/templates/* routes, and re-exports it under the same name.

This file is designed to be as minimal as possible to avoid any
import failures that would prevent the server from starting.
"""

import os
import sys
import importlib.util

# ---------------------------------------------------------------------------
# Load the upstream server.py WITHOUT going through the package system.
# We locate it by walking sys.path, skipping this file itself.
# ---------------------------------------------------------------------------
_THIS = os.path.abspath(__file__)
_upstream_server = None

for _entry in sys.path:
    _candidate = os.path.join(_entry, "astrbot", "dashboard", "server.py")
    _candidate = os.path.abspath(_candidate)
    if os.path.isfile(_candidate) and _candidate != _THIS:
        _upstream_server = _candidate
        break

if _upstream_server:
    # Load upstream server under a private module name
    _spec = importlib.util.spec_from_file_location(
        "_upstream_astrbot_dashboard_server", _upstream_server
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _UpstreamDashboard = _mod.AstrBotDashboard

    # Load templates_api directly from our file (avoids package __init__ issues)
    _tapi_path = os.path.join(os.path.dirname(_THIS), "routes", "templates_api.py")
    _tapi_spec = importlib.util.spec_from_file_location(
        "_templates_api", _tapi_path
    )
    _tapi = importlib.util.module_from_spec(_tapi_spec)
    _tapi_spec.loader.exec_module(_tapi)
    _register = _tapi.register_template_routes

    class AstrBotDashboard(_UpstreamDashboard):
        """Upstream AstrBotDashboard + /api/templates/* routes."""

        def __init__(self, core_lifecycle, db, shutdown_event):
            super().__init__(core_lifecycle, db, shutdown_event)

            # Exempt /api/templates from JWT auth
            from quart import request as _req

            @self.app.before_request
            async def _allow_templates():
                if _req.path.startswith("/api/templates"):
                    return None

            # Register our template routes
            _register(self.app, db)

else:
    # Fallback: upstream server.py is at the same path as this file
    # (i.e. we ARE the upstream file after COPY).  Import everything
    # the upstream server.py would have imported and define the full class.
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
    from astrbot.core import logger, WEBUI_SK
    from astrbot.core.db import BaseDatabase
    from astrbot.core.utils.io import get_local_ip_addresses
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path

    # Load templates_api directly to avoid any package __init__ issues
    _tapi_path = os.path.join(os.path.dirname(_THIS), "routes", "templates_api.py")
    _tapi_spec = importlib.util.spec_from_file_location("_templates_api", _tapi_path)
    _tapi = importlib.util.module_from_spec(_tapi_spec)
    _tapi_spec.loader.exec_module(_tapi)
    _register = _tapi.register_template_routes

    class AstrBotDashboard:  # noqa: F811
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
            _register(self.app, db)
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
            allowed_endpoints = [
                "/api/auth/login",
                "/api/file",
                "/api/templates",
            ]
            if any(request.path.startswith(p) for p in allowed_endpoints):
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
            except Exception:
                return True

        def get_process_using_port(self, port: int) -> str:
            return "unknown"

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

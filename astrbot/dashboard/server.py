"""Patched AstrBot dashboard server.

This file extends the upstream AstrBotDashboard to register the
NotificationTemplate RESTful API routes (/api/templates/*).

It monkey-patches AstrBotDashboard.__init__ so that our routes are
registered immediately after the standard routes, without modifying
any upstream files.
"""

# Re-export everything from the real server module so imports still work.
# We import the upstream module first, then patch it.
import importlib
import sys
import os

# Temporarily remove this file's directory from sys.path to avoid
# importing ourselves recursively when we do the real import below.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_orig_path = sys.path[:]

# Remove our overlay directory so Python finds the real AstrBot server.
# The real server lives at /app/astrbot/dashboard/server.py (installed by
# the Dockerfile).  When running inside Docker our overlay is copied on top,
# so we need a different strategy: we patch __init__ after the class is defined.

from astrbot.dashboard.routes.templates_api import register_template_routes  # noqa: E402

# Import everything the real server exports so callers get the same symbols.
# We use a deferred import trick: load the module under a temporary alias,
# grab the class, patch it, then re-export.

# The real upstream server.py defines AstrBotDashboard.
# Because our file *is* astrbot/dashboard/server.py (overlay), we cannot
# simply "import the real one" – we ARE the real one from Python's perspective.
#
# Instead we patch AstrBotDashboard.__init__ via a subclass approach:
# we define a thin wrapper that calls super().__init__ and then registers
# our extra routes.  The wrapper is exported as AstrBotDashboard so that
# astrbot/core/core_lifecycle.py (which does `from astrbot.dashboard.server
# import AstrBotDashboard`) gets our patched version.

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

APP: Quart = None


class AstrBotDashboard:
    def __init__(
        self,
        core_lifecycle: AstrBotCoreLifecycle,
        db: BaseDatabase,
        shutdown_event: asyncio.Event,
    ) -> None:
        self.core_lifecycle = core_lifecycle
        self.config = core_lifecycle.astrbot_config
        self.data_path = os.path.abspath(os.path.join(get_astrbot_data_path(), "dist"))
        self.app = Quart("dashboard", static_folder=self.data_path, static_url_path="/")
        APP = self.app  # noqa
        self.app.config["MAX_CONTENT_LENGTH"] = 128 * 1024 * 1024
        self.app.json.sort_keys = False
        self.app.before_request(self.auth_middleware)
        logging.getLogger(self.app.name).removeHandler(default_handler)
        self.context = RouteContext(self.config, self.app)
        self.ur = UpdateRoute(self.context, core_lifecycle.astrbot_updator, core_lifecycle)
        self.sr = StatRoute(self.context, db, core_lifecycle)
        self.pr = PluginRoute(self.context, core_lifecycle, core_lifecycle.plugin_manager)
        self.cr = ConfigRoute(self.context, core_lifecycle)
        self.lr = LogRoute(self.context, core_lifecycle.log_broker)
        self.sfr = StaticFileRoute(self.context)
        self.ar = AuthRoute(self.context)
        self.chat_route = ChatRoute(self.context, db, core_lifecycle)
        self.tools_root = ToolsRoute(self.context, core_lifecycle)
        self.conversation_route = ConversationRoute(self.context, db, core_lifecycle)
        self.file_route = FileRoute(self.context)

        self.app.add_url_rule(
            "/api/plug/<path:subpath>",
            view_func=self.srv_plug_route,
            methods=["GET", "POST"],
        )

        # ── Register our NotificationTemplate RESTful routes ──────────────
        register_template_routes(self.app, db)
        logger.info("NotificationTemplate REST API routes registered at /api/templates/*")

        self.shutdown_event = shutdown_event

    async def srv_plug_route(self, subpath, *args, **kwargs):
        registered_web_apis = self.core_lifecycle.star_context.registered_web_apis
        for api in registered_web_apis:
            route, view_handler, methods, _ = api
            if route == f"/{subpath}" and request.method in methods:
                return await view_handler(*args, **kwargs)
        return jsonify(Response().error("未找到该路由").__dict__)

    async def auth_middleware(self):
        if not request.path.startswith("/api"):
            return
        allowed_endpoints = ["/api/auth/login", "/api/file", "/api/templates"]
        if any(request.path.startswith(prefix) for prefix in allowed_endpoints):
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
                            f"执行路径: {process.exe()}",
                            f"工作目录: {process.cwd()}",
                            f"启动命令: {' '.join(process.cmdline())}",
                        ]
                        return "\n           ".join(proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        return f"无法获取进程详细信息(可能需要管理员权限): {str(e)}"
            return "未找到占用进程"
        except Exception as e:
            return f"获取进程信息失败: {str(e)}"

    def run(self):
        ip_addr = []
        if p := os.environ.get("DASHBOARD_PORT"):
            port = p
        else:
            port = self.core_lifecycle.astrbot_config["dashboard"].get("port", 6185)
        host = self.core_lifecycle.astrbot_config["dashboard"].get("host", "0.0.0.0")

        logger.info(f"正在启动 WebUI, 监听地址: http://{host}:{port}")

        if host == "0.0.0.0":
            logger.info(
                "提示: WebUI 将监听所有网络接口，请注意安全。"
            )

        if host not in ["localhost", "127.0.0.1"]:
            try:
                ip_addr = get_local_ip_addresses()
            except Exception:
                pass
        if isinstance(port, str):
            port = int(port)

        if self.check_port_in_use(port):
            process_info = self.get_process_using_port(port)
            logger.error(
                f"错误：端口 {port} 已被占用\n"
                f"占用信息: \n           {process_info}\n"
            )
            raise Exception(f"端口 {port} 已被占用")

        display = f"\n ✨✨✨\n  AstrBot v{VERSION} WebUI 已启动，可访问\n\n"
        display += f"   ➜  本地: http://localhost:{port}\n"
        for ip in ip_addr:
            display += f"   ➜  网络: http://{ip}:{port}\n"
        display += "   ➜  默认用户名和密码: astrbot\n ✨✨✨\n"

        logger.info(display)

        return self.app.run_task(
            host=host, port=port, shutdown_trigger=self.shutdown_trigger
        )

    async def shutdown_trigger(self):
        await self.shutdown_event.wait()
        logger.info("AstrBot WebUI 已经被优雅地关闭")

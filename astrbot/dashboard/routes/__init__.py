# Re-export all upstream AstrBot dashboard routes so server.py can import them.
# We also export our new NotificationTemplateRoute and register_template_routes.

from .auth import AuthRoute
from .plugin import PluginRoute
from .config import ConfigRoute
from .update import UpdateRoute
from .stat import StatRoute
from .log import LogRoute
from .static_file import StaticFileRoute
from .chat import ChatRoute
from .tools import ToolsRoute
from .conversation import ConversationRoute
from .file import FileRoute

# Our additions
from .notification_template import NotificationTemplateRoute
from .templates_api import register_template_routes

# StaticRoute lives in the parent package to avoid circular imports.
def __getattr__(name):
    if name == "StaticRoute":
        from astrbot.dashboard.static_route import StaticRoute
        return StaticRoute
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "AuthRoute",
    "PluginRoute",
    "ConfigRoute",
    "UpdateRoute",
    "StatRoute",
    "LogRoute",
    "StaticFileRoute",
    "ChatRoute",
    "ToolsRoute",
    "ConversationRoute",
    "FileRoute",
    # Our additions
    "NotificationTemplateRoute",
    "register_template_routes",
    "StaticRoute",
]

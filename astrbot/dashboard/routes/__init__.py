"""AstrBot dashboard routes package – overlay additions.

When Docker copies our astrbot/ overlay on top of the cloned AstrBot,
this file replaces the upstream astrbot/dashboard/routes/__init__.py.

IMPORTANT: We must re-export everything the upstream __init__.py exported,
because astrbot/dashboard/server.py does ``from .routes import *``.

Upstream exports (from AstrBot v3.5.16):
    AuthRoute, PluginRoute, ConfigRoute, UpdateRoute, StatRoute,
    LogRoute, StaticFileRoute, ChatRoute, ToolsRoute, ConversationRoute,
    FileRoute

Our additions:
    NotificationTemplateRoute, register_template_routes
"""

# Re-export all upstream route classes.  These modules exist in the Docker
# image at /app/astrbot/dashboard/routes/ (cloned from AstrBot v3.5.16).
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

# Our new additions (files we added in this overlay)
from .notification_template import NotificationTemplateRoute
from .templates_api import register_template_routes

__all__ = [
    # Upstream
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
]

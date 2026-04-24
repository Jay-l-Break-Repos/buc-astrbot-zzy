from .notification_template import NotificationTemplateRoute
from .templates_api import register_template_routes

# StaticRoute lives in the parent dashboard package to avoid circular imports.
# Re-export it here so callers can do:
#   from astrbot.dashboard.routes import StaticRoute
def __getattr__(name):
    if name == "StaticRoute":
        from astrbot.dashboard.static_route import StaticRoute
        return StaticRoute
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "NotificationTemplateRoute",
    "register_template_routes",
    "StaticRoute",
]

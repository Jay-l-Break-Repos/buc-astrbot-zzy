# AstrBot dashboard package
from .static_route import StaticRoute
from .routes import NotificationTemplateRoute, register_template_routes

__all__ = ["StaticRoute", "NotificationTemplateRoute", "register_template_routes"]

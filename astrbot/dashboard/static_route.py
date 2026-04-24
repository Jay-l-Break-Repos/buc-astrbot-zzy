"""Static file route for the Notification Templates management page.

Serves the single-page HTML UI at:
    GET /notification_templates
"""

import os
from quart import send_from_directory
from .routes.route import Route, RouteContext


class StaticRoute(Route):
    """Serves static HTML pages for the AstrBot dashboard."""

    _STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = {
            "/notification_templates": ("GET", self.serve_notification_templates),
        }
        self._register_static_routes()

    def _register_static_routes(self):
        """Register static page routes directly on the Quart app."""
        for route, (method, func) in self.routes.items():
            self.app.add_url_rule(route, view_func=func, methods=[method])

    async def serve_notification_templates(self):
        """Serve the notification templates management HTML page."""
        return await send_from_directory(self._STATIC_DIR, "notification_templates.html")

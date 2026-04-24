"""Dashboard static-file serving route.

Registers a GET endpoint that serves the notification template management UI:

    GET /notification_templates
        → serves astrbot/dashboard/static/notification_templates.html
"""

import os
from quart import send_from_directory
from .routes.route import Route, RouteContext


class StaticRoute(Route):
    """Serves static HTML pages for the AstrBot dashboard."""

    # Directory containing static assets (same folder as this file)
    _STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = {
            "/notification_templates": ("GET", self.serve_notification_templates),
        }
        self.register_routes()

    async def serve_notification_templates(self):
        """Serve the notification template management SPA."""
        return await send_from_directory(self._STATIC_DIR, "notification_templates.html")

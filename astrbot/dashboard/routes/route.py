"""Base Route class and shared types for AstrBot dashboard routes."""

from dataclasses import dataclass, field
from typing import Any
from quart import Quart


@dataclass
class RouteContext:
    config: Any
    app: Quart


@dataclass
class Response:
    status: bool = True
    message: str = ""
    data: Any = None

    def ok(self, message: str = "", data: Any = None) -> "Response":
        self.status = True
        self.message = message
        self.data = data
        return self

    def error(self, message: str = "", data: Any = None) -> "Response":
        self.status = False
        self.message = message
        self.data = data
        return self


class Route:
    def __init__(self, context: RouteContext) -> None:
        self.context = context
        self.config = context.config
        self.app = context.app

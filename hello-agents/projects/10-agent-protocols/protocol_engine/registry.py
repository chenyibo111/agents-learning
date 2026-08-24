"""Explicit capability registries for tools and allowlisted resources."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from .auth import AuthContext, Authorizer
from .contracts import ResourceDefinition, ToolDefinition
from .errors import ErrorCode, ProtocolError


class CapabilityRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._resources: dict[str, ResourceDefinition] = {}

    def register_tool(
        self,
        name: str,
        handler: Callable[[dict[str, Any]], Any],
        *,
        description: str,
        input_schema: dict[str, Any] | None = None,
        required_scopes: Iterable[str] = (),
    ) -> None:
        if name in self._tools:
            raise ValueError(f"工具已注册：{name}")
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema or {"type": "object"},
            handler=handler,
            required_scopes=frozenset(required_scopes),
        )

    def register_resource(
        self,
        uri: str,
        content: str | Callable[[], str],
        *,
        description: str,
        mime_type: str = "text/plain",
        required_scopes: Iterable[str] = (),
    ) -> None:
        if not uri or uri in self._resources:
            raise ValueError(f"资源 URI 无效或重复：{uri}")
        self._resources[uri] = ResourceDefinition(
            uri=uri,
            description=description,
            content=content,
            mime_type=mime_type,
            required_scopes=frozenset(required_scopes),
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return [self._tools[name].to_dict() for name in sorted(self._tools)]

    def list_resources(self) -> list[dict[str, Any]]:
        return [self._resources[uri].to_dict() for uri in sorted(self._resources)]

    def get_tool(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ProtocolError(ErrorCode.TOOL_NOT_FOUND, "工具不存在") from exc

    def get_resource(self, uri: str) -> ResourceDefinition:
        try:
            return self._resources[uri]
        except KeyError as exc:
            raise ProtocolError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在") from exc

    def call_tool(self, name: str, arguments: Any, context: AuthContext) -> Any:
        tool = self.get_tool(name)
        Authorizer.require(context, tool.required_scopes)
        return tool.handler(tool.validate_arguments(arguments))

    def read_resource(self, uri: str, context: AuthContext) -> ResourceDefinition:
        resource = self.get_resource(uri)
        Authorizer.require(context, resource.required_scopes)
        return resource

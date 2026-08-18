"""Registration and dispatch layer for tools and resources."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from protocol import INVALID_PARAMS, ProtocolError


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(frozen=True)
class ResourceDefinition:
    uri: str
    name: str
    description: str
    mime_type: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mime_type": self.mime_type,
        }


class ToolResourceRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, tuple[ToolDefinition, Callable[..., Any]]] = {}
        self._resources: Dict[str, tuple[ResourceDefinition, Callable[[str], str]]] = {}

    def register_tool(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Any],
    ) -> None:
        if definition.name in self._tools:
            raise ValueError(f"工具已注册：{definition.name}")
        self._tools[definition.name] = (definition, handler)

    def register_resource(
        self,
        definition: ResourceDefinition,
        reader: Callable[[str], str],
    ) -> None:
        if definition.uri in self._resources:
            raise ValueError(f"资源已注册：{definition.uri}")
        self._resources[definition.uri] = (definition, reader)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [definition.to_dict() for definition, _ in self._tools.values()]

    def list_resources(self) -> List[Dict[str, str]]:
        return [definition.to_dict() for definition, _ in self._resources.values()]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name not in self._tools:
            raise ProtocolError(INVALID_PARAMS, f"未知工具：{name}")
        if not isinstance(arguments, dict):
            raise ProtocolError(INVALID_PARAMS, "工具 arguments 必须是对象")

        definition, handler = self._tools[name]
        self._validate_arguments(definition.input_schema, arguments)
        return handler(**arguments)

    def read_resource(self, uri: str) -> str:
        if uri not in self._resources:
            raise ProtocolError(INVALID_PARAMS, f"未知资源：{uri}")
        _, reader = self._resources[uri]
        return reader(uri)

    def _validate_arguments(
        self,
        schema: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> None:
        if schema.get("type") != "object":
            raise ProtocolError(INVALID_PARAMS, "工具 Schema 必须是 object")

        required = schema.get("required", [])
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ProtocolError(
                INVALID_PARAMS,
                f"缺少必填参数：{', '.join(missing)}",
            )

        properties = schema.get("properties", {})
        for name, value in arguments.items():
            expected_type = properties.get(name, {}).get("type")
            if expected_type and not _matches_type(value, expected_type):
                raise ProtocolError(
                    INVALID_PARAMS,
                    f"参数 {name} 的类型不正确，期望 {expected_type}",
                )


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True

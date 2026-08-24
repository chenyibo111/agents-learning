"""Tool definitions, registration and defensive argument validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .errors import PermissionDeniedError, ToolNotFoundError, ToolValidationError


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]
    permission: str = ""
    retryable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    """Registry that prevents invalid or unauthorized tool execution."""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        if not spec.name.strip():
            raise ValueError("tool name 不能为空")
        if spec.name in self._tools:
            raise ValueError(f"工具已注册：{spec.name}")
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"未知工具：{name}") from exc

    def schemas(self) -> list[dict[str, Any]]:
        return [spec.schema() for spec in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        allowed_permissions: set[str] | frozenset[str],
    ) -> Any:
        spec = self.get(name)
        if spec.permission and spec.permission not in allowed_permissions:
            raise PermissionDeniedError(
                f"没有执行工具 {name} 所需权限：{spec.permission}"
            )
        self._validate_arguments(spec, arguments)
        return spec.handler(**arguments)

    def tool(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        permission: str = "",
        retryable: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Return a decorator that registers a function as a ToolSpec."""

        def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
            self.register(
                ToolSpec(
                    name=name,
                    description=description,
                    input_schema=input_schema,
                    handler=function,
                    permission=permission,
                    retryable=retryable,
                )
            )
            return function

        return decorator

    @staticmethod
    def _validate_arguments(spec: ToolSpec, arguments: Any) -> None:
        if not isinstance(arguments, dict):
            raise ToolValidationError(f"工具 {spec.name} 参数必须是 object")

        schema = spec.input_schema
        if schema.get("type", "object") != "object":
            raise ToolValidationError(f"工具 {spec.name} schema 必须是 object")

        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [key for key in required if key not in arguments]
        if missing:
            raise ToolValidationError(
                f"工具 {spec.name} 缺少参数：{', '.join(missing)}"
            )

        if schema.get("additionalProperties") is False:
            unknown = [key for key in arguments if key not in properties]
            if unknown:
                raise ToolValidationError(
                    f"工具 {spec.name} 存在未知参数：{', '.join(unknown)}"
                )

        for key, value in arguments.items():
            if key not in properties:
                continue
            expected = properties[key].get("type")
            if expected and not ToolRegistry._matches_type(value, expected):
                raise ToolValidationError(
                    f"工具 {spec.name} 参数 {key} 类型错误，期望 {expected}"
                )

    @staticmethod
    def _matches_type(value: Any, expected: str) -> bool:
        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected == "string":
            return isinstance(value, str)
        if expected == "boolean":
            return isinstance(value, bool)
        if expected == "array":
            return isinstance(value, list)
        if expected == "object":
            return isinstance(value, dict)
        return True

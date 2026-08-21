"""Protocol method routing, validation, and error normalization."""

from typing import Any, Dict

from protocol import (
    EXECUTION_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    ProtocolError,
    ProtocolResponse,
    decode_request,
)
from registry import ToolResourceRegistry


class ProtocolServer:
    def __init__(self, registry: ToolResourceRegistry) -> None:
        self.registry = registry

    def handle(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        try:
            request = decode_request(raw_request)
        except ProtocolError as error:
            return ProtocolResponse.failure(
                None,
                error.code,
                error.message,
                error.data,
            ).to_dict()

        try:
            result = self._dispatch(request.method, request.params)
            return ProtocolResponse.success(request.request_id, result).to_dict()
        except ProtocolError as error:
            return ProtocolResponse.failure(
                request.request_id,
                error.code,
                error.message,
                error.data,
            ).to_dict()
        except Exception:
            return ProtocolResponse.failure(
                request.request_id,
                EXECUTION_ERROR,
                "工具执行失败",
            ).to_dict()

    def _dispatch(self, method: str, params: Dict[str, Any]) -> Any:
        if method == "tools/list":
            return self.registry.list_tools()
        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments")
            if not isinstance(name, str) or not name.strip():
                raise ProtocolError(INVALID_PARAMS, "tools/call 缺少有效 name")
            if not isinstance(arguments, dict):
                raise ProtocolError(INVALID_PARAMS, "tools/call 缺少有效 arguments")
            return self.registry.call_tool(name, arguments)
        if method == "resources/list":
            return self.registry.list_resources()
        if method == "resources/read":
            uri = params.get("uri")
            if not isinstance(uri, str) or not uri.strip():
                raise ProtocolError(INVALID_PARAMS, "resources/read 缺少有效 uri")
            return {
                "uri": uri,
                "contents": self.registry.read_resource(uri),
            }
        raise ProtocolError(METHOD_NOT_FOUND, f"未知方法：{method}")

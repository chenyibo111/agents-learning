import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1] / "projects" / "23-agent-protocol"


def load_module(module_name: str):
    source_file = PROJECT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


protocol = load_module("protocol")
registry_module = load_module("registry")
business_module = load_module("business")
server_module = load_module("server")
main_module = load_module("main")


class ProtocolTests(unittest.TestCase):
    def test_request_round_trip_preserves_fields(self) -> None:
        request = protocol.ProtocolRequest(
            request_id=1,
            method="tools/list",
            params={},
        )

        decoded = protocol.decode_request(
            protocol.encode_message(request.to_dict())
        )

        self.assertEqual(decoded.request_id, 1)
        self.assertEqual(decoded.method, "tools/list")
        self.assertEqual(decoded.params, {})

    def test_invalid_request_has_protocol_error(self) -> None:
        with self.assertRaises(protocol.ProtocolError) as context:
            protocol.decode_request('{"id": 1, "params": {}}')

        self.assertEqual(context.exception.code, protocol.INVALID_REQUEST)

    def test_response_can_encode_success_and_error(self) -> None:
        success = protocol.ProtocolResponse.success(1, {"ok": True})
        failure = protocol.ProtocolResponse.failure(
            1,
            protocol.INVALID_PARAMS,
            "参数无效",
        )

        success_message = protocol.decode_message(
            protocol.encode_message(success.to_dict())
        )
        failure_message = protocol.decode_message(
            protocol.encode_message(failure.to_dict())
        )

        self.assertEqual(success_message["result"], {"ok": True})
        self.assertEqual(
            failure_message["error"]["code"],
            protocol.INVALID_PARAMS,
        )


class RegistryTests(unittest.TestCase):
    def test_registry_lists_tool_schema_and_resource_metadata(self) -> None:
        registry = business_module.build_registry()

        tools = registry.list_tools()
        resources = registry.list_resources()

        self.assertEqual(tools[0]["name"], "add_numbers")
        self.assertEqual(tools[0]["input_schema"]["required"], ["a", "b"])
        self.assertEqual(resources[0]["uri"], "note://agent-basics")
        self.assertEqual(resources[0]["mime_type"], "text/markdown")

    def test_invalid_arguments_do_not_call_handler(self) -> None:
        calls = []
        registry = registry_module.ToolResourceRegistry()
        registry.register_tool(
            registry_module.ToolDefinition(
                name="record",
                description="record two integers",
                input_schema={
                    "type": "object",
                    "required": ["a", "b"],
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                },
            ),
            lambda **arguments: calls.append(arguments),
        )

        with self.assertRaises(protocol.ProtocolError) as context:
            registry.call_tool("record", {"a": 1})

        self.assertEqual(context.exception.code, protocol.INVALID_PARAMS)
        self.assertEqual(calls, [])


class ServerTests(unittest.TestCase):
    def test_server_routes_tool_and_resource_operations(self) -> None:
        server = server_module.ProtocolServer(business_module.build_registry())

        tools = server.handle(
            {"id": 1, "method": "tools/list", "params": {}}
        )
        resources = server.handle(
            {"id": 2, "method": "resources/list", "params": {}}
        )
        result = server.handle(
            {
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "add_numbers",
                    "arguments": {"a": 2, "b": 3},
                },
            }
        )
        resource = server.handle(
            {
                "id": 4,
                "method": "resources/read",
                "params": {"uri": "note://agent-basics"},
            }
        )

        self.assertIn("add_numbers", [item["name"] for item in tools["result"]])
        self.assertIn(
            "note://agent-basics",
            [item["uri"] for item in resources["result"]],
        )
        self.assertEqual(result["result"]["sum"], 5)
        self.assertIn("Agent", resource["result"]["contents"])

    def test_server_returns_method_and_argument_errors_without_traceback(self) -> None:
        server = server_module.ProtocolServer(business_module.build_registry())

        unknown = server.handle(
            {"id": 4, "method": "tools/delete", "params": {}}
        )
        invalid = server.handle(
            {
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "add_numbers",
                    "arguments": {"a": 2},
                },
            }
        )

        self.assertEqual(unknown["error"]["code"], protocol.METHOD_NOT_FOUND)
        self.assertEqual(invalid["error"]["code"], protocol.INVALID_PARAMS)
        self.assertNotIn("Traceback", str(invalid))

    def test_business_failure_is_wrapped_as_execution_error(self) -> None:
        registry = registry_module.ToolResourceRegistry()
        registry.register_tool(
            registry_module.ToolDefinition(
                name="explode",
                description="raise an exception",
                input_schema={"type": "object"},
            ),
            lambda **_: 1 / 0,
        )
        server = server_module.ProtocolServer(registry)

        response = server.handle(
            {
                "id": 6,
                "method": "tools/call",
                "params": {"name": "explode", "arguments": {}},
            }
        )

        self.assertEqual(response["error"]["code"], protocol.EXECUTION_ERROR)
        self.assertNotIn("ZeroDivisionError", response["error"]["message"])

    def test_unknown_resource_uri_is_rejected_without_filesystem_access(self) -> None:
        registry = business_module.build_registry()

        with self.assertRaises(protocol.ProtocolError) as context:
            registry.read_resource("file:///etc/passwd")

        self.assertEqual(context.exception.code, protocol.INVALID_PARAMS)


class DemoTests(unittest.TestCase):
    def test_demo_request_crosses_json_boundary(self) -> None:
        server = server_module.ProtocolServer(business_module.build_registry())
        response = main_module.request(
            server,
            {
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "add_numbers",
                    "arguments": {"a": 4, "b": 6},
                },
            },
        )

        self.assertEqual(response["result"]["sum"], 10)


if __name__ == "__main__":
    unittest.main()

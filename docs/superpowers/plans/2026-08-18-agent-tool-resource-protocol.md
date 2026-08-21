# Agent Tool and Resource Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python, offline, MCP-inspired JSON protocol demo that separates Agent communication, tool/resource dispatch, and business handlers.

**Architecture:** `protocol.py` owns wire data structures and JSON validation. `registry.py` owns handler registration and argument validation. `server.py` maps four protocol methods to the registry and normalizes errors. `business.py` contains only safe in-memory handlers, while `main.py` demonstrates a client crossing the JSON encode/decode boundary.

**Tech Stack:** Python 3.9+ standard library, `dataclasses`, `json`, `unittest`; no LLM, network service, API key, or third-party dependency.

**User constraint:** Do not create Git commits. All plan, lesson, project, and test changes remain in the working tree for user review.

---

## File map

- Create: `projects/23-agent-protocol/protocol.py` — request/response envelopes, tool/resource definitions, JSON conversion, protocol error codes.
- Create: `projects/23-agent-protocol/registry.py` — registrations, argument validation, handler invocation.
- Create: `projects/23-agent-protocol/server.py` — `tools/list`, `tools/call`, `resources/list`, `resources/read` routing.
- Create: `projects/23-agent-protocol/business.py` — in-memory notes and safe teaching handlers.
- Create: `projects/23-agent-protocol/main.py` — offline JSON round-trip demo and CLI.
- Create: `projects/23-agent-protocol/README.md` — running instructions and layer explanation.
- Create: `projects/23-agent-protocol/requirements.txt` — empty dependency declaration.
- Create: `tests/test_agent_protocol.py` — protocol, registry, server, and security-boundary tests.
- Modify: `lessons/23-agent-protocol.md` — add implementation walkthrough and learning exercises after code exists.
- Modify: `CURRICULUM.md` — point lesson 23 to the lesson and project, mark as generated/waiting for study.
- Modify: `README.md` and `ROADMAP.md` — update the current lesson range after the project is generated.

## Task 1: Protocol data model and JSON boundary

**Files:**
- Create: `projects/23-agent-protocol/protocol.py`
- Test: `tests/test_agent_protocol.py`

- [x] **Step 1: Write failing tests for protocol envelopes.**

Create a test module that loads the project module by file path, matching the repository's existing unittest style. Start with these tests:

```python
def test_request_round_trip_preserves_fields(self):
    request = protocol.ProtocolRequest(
        request_id=1,
        method="tools/list",
        params={},
    )

    decoded = protocol.decode_request(protocol.encode_message(request.to_dict()))

    self.assertEqual(decoded.request_id, 1)
    self.assertEqual(decoded.method, "tools/list")
    self.assertEqual(decoded.params, {})

def test_invalid_request_has_protocol_error(self):
    with self.assertRaises(protocol.ProtocolError) as context:
        protocol.decode_request('{"id": 1, "params": {}}')

    self.assertEqual(context.exception.code, protocol.INVALID_REQUEST)

def test_response_can_encode_success_and_error(self):
    success = protocol.ProtocolResponse.success(1, {"ok": True})
    failure = protocol.ProtocolResponse.failure(
        1,
        protocol.INVALID_PARAMS,
        "参数无效",
    )

    self.assertEqual(protocol.decode_message(protocol.encode_message(success.to_dict()))["result"], {"ok": True})
    self.assertEqual(protocol.decode_message(protocol.encode_message(failure.to_dict()))["error"]["code"], protocol.INVALID_PARAMS)
```

- [x] **Step 2: Run the focused test and verify it fails.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: FAIL because `projects/23-agent-protocol/protocol.py` and the protocol types do not exist yet.

- [x] **Step 3: Implement the minimal protocol module.**

Define these exact public names:

```python
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
EXECUTION_ERROR = -32001

@dataclass(frozen=True)
class ProtocolError(Exception):
    code: int
    message: str
    data: Any = None

@dataclass(frozen=True)
class ProtocolRequest:
    request_id: Any
    method: str
    params: dict[str, Any]

@dataclass(frozen=True)
class ProtocolResponse:
    request_id: Any
    result: Any = None
    error: Optional[dict[str, Any]] = None
```

`decode_message` must parse one JSON object only. `decode_request` must reject missing `id`, non-string/empty `method`, and non-object `params` by raising `ProtocolError(INVALID_REQUEST, ...)`. `encode_message` must call `json.dumps(..., ensure_ascii=False, sort_keys=True)` and never serialize Python exceptions or tracebacks.

- [x] **Step 4: Run the focused tests and verify they pass.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: the three protocol tests pass; later tests may still fail because the registry and server are not implemented.

## Task 2: Tool/resource definitions, registry, and business handlers

**Files:**
- Modify: `tests/test_agent_protocol.py`
- Create: `projects/23-agent-protocol/registry.py`
- Create: `projects/23-agent-protocol/business.py`

- [x] **Step 1: Add failing tests for definitions, validation, and safe resources.**

Add tests with observable handler call counters:

```python
def test_registry_lists_tool_schema_and_resource_metadata(self):
    registry = build_registry()

    tools = registry.list_tools()
    resources = registry.list_resources()

    self.assertEqual(tools[0]["name"], "add_numbers")
    self.assertEqual(tools[0]["input_schema"]["required"], ["a", "b"])
    self.assertEqual(resources[0]["uri"], "note://agent-basics")
    self.assertEqual(resources[0]["mime_type"], "text/markdown")

def test_invalid_arguments_do_not_call_handler(self):
    calls = []
    registry = registry_module.ToolResourceRegistry()
    registry.register_tool(
        registry_module.ToolDefinition(
            name="record",
            description="record two integers",
            input_schema={
                "type": "object",
                "required": ["a", "b"],
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            },
        ),
        lambda **arguments: calls.append(arguments),
    )

    with self.assertRaises(protocol.ProtocolError) as context:
        registry.call_tool("record", {"a": 1})

    self.assertEqual(context.exception.code, protocol.INVALID_PARAMS)
    self.assertEqual(calls, [])

def test_unknown_resource_uri_is_rejected_without_filesystem_access(self):
    registry = build_registry()

    with self.assertRaises(protocol.ProtocolError) as context:
        registry.read_resource("file:///etc/passwd")

    self.assertEqual(context.exception.code, protocol.INVALID_PARAMS)
```

- [x] **Step 2: Run the focused tests and verify the new tests fail.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: FAIL because the registry, definitions, and `build_registry` fixture do not exist.

- [x] **Step 3: Implement the registry and in-memory business layer.**

`registry.py` must expose `ToolDefinition`, `ResourceDefinition`, and `ToolResourceRegistry`. `register_tool` and `register_resource` must reject duplicate names/URIs. `call_tool` must validate an object argument against the schema's required fields and primitive `integer`, `number`, `string`, and `boolean` types before calling the handler. `read_resource` must perform exact URI lookup only.

`business.py` must define a constant in-memory notes mapping and these functions:

```python
def add_numbers(a: int, b: int) -> dict[str, Any]:
    return {"a": a, "b": b, "sum": a + b}

def search_notes(query: str) -> list[dict[str, str]]:
    query_terms = {term.lower() for term in query.split() if term}
    return [note for note in NOTES if query_terms & set(note["keywords"])]

def read_note(uri: str) -> str:
    return NOTES_BY_URI[uri]["content"]
```

`build_registry()` must register `add_numbers`, `search_notes`, and the two fixed note resources using only the in-memory handlers.

- [x] **Step 4: Run the focused tests and verify they pass.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: protocol and registry tests pass; server-routing tests are the only remaining failures.

## Task 3: Protocol server routing and normalized errors

**Files:**
- Modify: `tests/test_agent_protocol.py`
- Create: `projects/23-agent-protocol/server.py`

- [x] **Step 1: Add failing tests for all four methods and error boundaries.**

Add tests using `ProtocolServer(build_registry())`:

```python
def test_server_routes_tool_and_resource_operations(self):
    server = server_module.ProtocolServer(build_registry())

    tools = server.handle({"id": 1, "method": "tools/list", "params": {}})
    result = server.handle({
        "id": 2,
        "method": "tools/call",
        "params": {"name": "add_numbers", "arguments": {"a": 2, "b": 3}},
    })
    resource = server.handle({
        "id": 3,
        "method": "resources/read",
        "params": {"uri": "note://agent-basics"},
    })

    self.assertIn("add_numbers", [item["name"] for item in tools["result"]])
    self.assertEqual(result["result"]["sum"], 5)
    self.assertIn("Agent", resource["result"]["contents"])

def test_server_returns_method_and_argument_errors_without_traceback(self):
    server = server_module.ProtocolServer(build_registry())

    unknown = server.handle({"id": 4, "method": "tools/delete", "params": {}})
    invalid = server.handle({
        "id": 5,
        "method": "tools/call",
        "params": {"name": "add_numbers", "arguments": {"a": 2}},
    })

    self.assertEqual(unknown["error"]["code"], protocol.METHOD_NOT_FOUND)
    self.assertEqual(invalid["error"]["code"], protocol.INVALID_PARAMS)
    self.assertNotIn("Traceback", str(invalid))

def test_business_failure_is_wrapped_as_execution_error(self):
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

    response = server.handle({
        "id": 6,
        "method": "tools/call",
        "params": {"name": "explode", "arguments": {}},
    })

    self.assertEqual(response["error"]["code"], protocol.EXECUTION_ERROR)
    self.assertNotIn("ZeroDivisionError", response["error"]["message"])
```

- [x] **Step 2: Run the focused tests and verify the routing tests fail.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: FAIL because `ProtocolServer` does not exist.

- [x] **Step 3: Implement the minimal server.**

`ProtocolServer.handle(raw_request: dict[str, Any]) -> dict[str, Any]` must call `decode_request`, dispatch exactly the four methods, and return `ProtocolResponse.to_dict()`. Dispatch rules:

- `tools/list` → `registry.list_tools()`;
- `tools/call` → require string `name` and object `arguments`, then `registry.call_tool`;
- `resources/list` → `registry.list_resources()`;
- `resources/read` → require string `uri`, then `registry.read_resource` and wrap it as `{"contents": text, "uri": uri}`.

Catch `ProtocolError` and return its code/message/data. Catch all other handler exceptions and return `EXECUTION_ERROR` with the generic message `工具执行失败` and no exception class or traceback. Preserve the request ID for valid requests; use `None` when request parsing cannot obtain one.

- [x] **Step 4: Run all protocol tests and verify they pass.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: all protocol tests pass.

## Task 4: Offline Demo, docs, and repository integration

**Files:**
- Modify: `tests/test_agent_protocol.py`
- Create: `projects/23-agent-protocol/main.py`
- Create: `projects/23-agent-protocol/README.md`
- Create: `projects/23-agent-protocol/requirements.txt`
- Modify: `lessons/23-agent-protocol.md`
- Modify: `CURRICULUM.md`
- Modify: `README.md`
- Modify: `ROADMAP.md`

- [x] **Step 1: Add failing tests for the JSON round-trip demo helper.**

Add one test that calls `main.request(server, payload)` and verifies it serializes the request, passes JSON through `ProtocolServer`, then decodes the response:

```python
def test_demo_request_crosses_json_boundary(self):
    server = server_module.ProtocolServer(build_registry())
    response = main_module.request(
        server,
        {"id": 7, "method": "tools/call", "params": {
            "name": "add_numbers", "arguments": {"a": 4, "b": 6}
        }},
    )

    self.assertEqual(response["result"]["sum"], 10)
```

- [x] **Step 2: Run the test and verify it fails.**

Run:

```bash
python3 -m unittest tests/test_agent_protocol.py -v
```

Expected: FAIL because the demo module/helper does not exist.

- [x] **Step 3: Implement the demo and documentation.**

`main.py` must expose:

```python
def request(server: ProtocolServer, payload: dict[str, Any]) -> dict[str, Any]:
    wire_request = encode_message(payload)
    decoded_request = decode_message(wire_request)
    response = server.handle(decoded_request)
    return decode_message(encode_message(response))
```

The `--demo` path must print, in order, tool discovery, resource discovery, successful tool call, resource read, unknown tool error, and invalid-argument error. It must not instantiate `OpenAI` or read environment variables. `requirements.txt` remains empty.

Extend `lessons/23-agent-protocol.md` with the file-by-file walkthrough, the request/response flow, and three exercises: add a `multiply` tool, add a second note resource, and make a test assert that a handler is not called for invalid input. Update the curriculum and roadmap links without marking unrelated lessons complete.

- [x] **Step 4: Run the full verification suite.**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPYCACHEPREFIX=/private/tmp/agents-learning-pycache-23 python3 -m compileall -q projects tests
python3 projects/23-agent-protocol/main.py --demo
git diff --check
```

Expected: all tests pass, compilation exits 0, the demo prints six protocol interactions, and `git diff --check` prints nothing. Do not run `git add` or `git commit`.

## Self-review checklist

- Protocol spec coverage: request validation, four methods, tool schemas, resource URIs, normalized errors, handler isolation, JSON round-trip, and offline demo are all covered by Tasks 1–4.
- Security boundary: resources use exact in-memory URI lookup; no arbitrary file path or shell execution is introduced.
- Type consistency: `ProtocolRequest`, `ProtocolResponse`, `ToolDefinition`, `ResourceDefinition`, `ToolResourceRegistry`, `ProtocolServer`, `build_registry`, and `request` are named consistently across tasks.
- No external secrets or network calls: the project uses no `.env`, `OpenAI`, HTTP client, or third-party package.
- User constraint honored: no commit step is included; all changes remain uncommitted for review.

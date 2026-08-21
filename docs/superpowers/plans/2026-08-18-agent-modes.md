# Dual Agent Modes Implementation Plan

**Goal:** Add a local rule-based Agent and an OpenAI-compatible tool-calling Agent without changing the existing `--demo` mode.

**Architecture:** Both Agent implementations send requests through the existing JSON protocol and `ProtocolServer`. The local Agent maps a small set of Chinese natural-language patterns to protocol requests. The LLM Agent discovers tools/resources, lets the model choose tool calls, executes every call through the protocol server, feeds results back to the model, and stops at a bounded number of rounds.

**User constraint:** Keep all existing demo behavior, preserve existing user-added tools/resources, and do not create Git commits.

## Task 1: Local rule-based Agent

Files:

- Create `projects/23-agent-protocol/agent.py`.
- Create `tests/test_agent_modes.py`.

TDD cases:

- `计算 12 加 30` routes to `add_numbers` and returns `42`.
- `计算 6 乘 7` routes to the multiplication tool and returns `42`.
- `搜索 工具 协议` routes to `search_notes`.
- `读取 Agent 基础` routes to `resources/read` for the matching registered URI.
- Unsupported input returns a capability hint without calling a handler.

The Agent must never import or call business functions directly. It must use the JSON request helper and render protocol success/error responses.

## Task 2: LLM tool-calling Agent

Files:

- Modify `projects/23-agent-protocol/agent.py` with the shared protocol client and LLM Agent.
- Create `tests/test_llm_agent.py` using a fake OpenAI-compatible client.

TDD cases:

- A model response with ordinary text ends the run and returns that text.
- A model response containing `add_numbers` tool call sends `tools/call` to the protocol server, then provides the tool result to the model for a final answer.
- A `read_resource` model tool call is translated into `resources/read`, not a direct file read.
- Invalid tool-call JSON becomes an error result and never reaches a business handler.
- Tool-call loops stop at `max_rounds`.

The LLM client is injected in tests. Runtime construction reads `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` only in LLM mode and never prints the key.

## Task 3: CLI modes, docs, and verification

Files:

- Modify `projects/23-agent-protocol/main.py` to add `--interactive` and `--agent {local,llm}` while leaving `--demo` intact.
- Modify `projects/23-agent-protocol/README.md` and `lessons/23-agent-protocol.md` with both modes and the LLM message loop.
- Modify `CURRICULUM.md`, `README.md`, and `ROADMAP.md` only if the current lesson description needs to mention dual modes.

Verification:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPYCACHEPREFIX=/private/tmp/agents-learning-pycache-agent-modes python3 -m compileall -q projects tests
python3 projects/23-agent-protocol/main.py --demo
python3 projects/23-agent-protocol/main.py --interactive --agent local
git diff --check
```

Do not run `git add` or `git commit`.

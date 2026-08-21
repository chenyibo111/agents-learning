# smolagents Agent Implementation Plan

**Goal:** Rebuild the lesson 23 capabilities as a small `smolagents` project and make the framework boundary visible through offline tests.

**Architecture:** `tools.py` contains framework-decorated business tools. `agent_runner.py` owns optional dependency checks, OpenAI-compatible model construction, and `ToolCallingAgent` creation. `main.py` provides an offline demo and a real interactive mode. The existing lesson 23 project remains unchanged.

**Dependency boundary:** Unit tests must run without `smolagents` or a live model. Real framework execution requires installing the project's `requirements.txt` and configuring the existing OpenAI-compatible environment variables.

## Task 1: Tool definitions and offline tests

- Create `projects/24-smolagents-agent/tools.py`.
- Create `tests/test_smolagents_agent.py`.
- Write failing tests for `add_numbers`, `mul_numbers`, `search_notes`, and resource lookup.
- Add a compatibility decorator only for import-time testing when `smolagents` is absent; real execution must still report the missing dependency.

## Task 2: Framework adapter

- Create `projects/24-smolagents-agent/agent_runner.py`.
- Test model configuration validation, missing dependency messaging, and tool collection without making a network request.
- Implement `build_model()` with `OpenAIServerModel` and `build_agent()` with `ToolCallingAgent`, `max_steps=6`.
- Keep API keys in environment variables and never print them.

## Task 3: Demo, interactive entry point, and documents

- Create `projects/24-smolagents-agent/main.py`, `README.md`, and `requirements.txt`.
- Add `--demo` for offline direct tool demonstrations and `--interactive` for the real framework Agent.
- Create `lessons/24-smolagents.md` explaining the comparison with lesson 23.
- Update `CURRICULUM.md`, `README.md`, and `ROADMAP.md` to link lesson 24.

## Verification

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPYCACHEPREFIX=/private/tmp/agents-learning-pycache-24 python3 -m compileall -q projects tests
python3 projects/24-smolagents-agent/main.py --demo
git diff --check
```

Do not create Git commits.

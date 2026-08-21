import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm, run_loop


def demo() -> str:
    def decide(state):
        return "add" if "result" not in state else "finish"
    def act(state, action):
        if action == "add":
            return {**state, "result": state["a"] + state["b"]}, "tool:add"
        return state, f"answer={state['result']}"
    result = run_loop({"a": 4, "b": 5}, decide, act, lambda s: "result" in s and result_safe(s), max_steps=3)
    return f"MiniFramework events={len(result.events)}; {result.answer}"


def result_safe(state):
    return isinstance(state.get("result"), int)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("设计一个最小 Agent Framework，说明 Model、Tool、Policy、Runner 的边界。") if args.llm else demo())


if __name__ == "__main__":
    main()

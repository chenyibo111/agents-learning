import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def demo() -> str:
    messages = [{"role": "system", "content": "只回答事实"}, {"role": "user", "content": "什么是上下文窗口？"}]
    prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    return f"消息数={len(messages)}；估算 token={estimate_tokens(prompt)}；模型输出必须经过程序校验。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("解释 token、上下文窗口和幻觉，并给出一个 Agent 工程建议。") if args.llm else demo())


if __name__ == "__main__":
    main()

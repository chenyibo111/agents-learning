import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm

DOCS = ["短期记忆保存当前会话。", "长期记忆保存稳定偏好。", "RAG 在请求时检索外部知识。"]


def retrieve(query: str, top_k: int = 2) -> list[str]:
    words = set(query)
    ranked = sorted(DOCS, key=lambda doc: len(words & set(doc)), reverse=True)
    return ranked[:top_k]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    if args.llm:
        print(ask_llm("解释短期记忆、长期记忆和 RAG 的边界。"))
    else:
        print({"hits": retrieve("长期记忆和 RAG")})


if __name__ == "__main__":
    main()

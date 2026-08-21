import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def research_demo() -> dict:
    sources = [{"id": "S1", "title": "本地文档", "evidence": "Agent 需要工具和状态。"}, {"id": "S2", "title": "评测记录", "evidence": "离线数据可用于回归。"}]
    claims = [{"text": "Agent 由模型、工具和状态组成", "source_ids": ["S1"]}, {"text": "离线评测适合回归", "source_ids": ["S2"]}]
    return {"sources": sources, "claims": claims, "rounds": 2}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("设计一个带来源、证据核对和预算的 DeepResearch 流程。") if args.llm else research_demo())


if __name__ == "__main__":
    main()

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm

from mcp_adapter import build_demo_server, run_demo
from protocol_engine.codec import decode_request
from protocol_engine.contracts import JsonRpcResponse
from protocol_engine.errors import ProtocolError


def make_task() -> dict:
    return {"protocol": "a2a-demo", "version": "1", "task_id": "demo-001", "capability": "summarize", "status": "submitted"}


def dispatch_request(payload: str, *, token: str = "demo-token") -> dict:
    """Dispatch one JSON-RPC request through a fresh local protocol server."""

    try:
        request = decode_request(payload)
    except ProtocolError as error:
        return JsonRpcResponse.failure(None, error).to_dict()
    return build_demo_server().handle(request, token=token).to_dict()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="第 10 课：MCP、A2A 与 ANP")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="运行离线协议工程 Demo")
    mode.add_argument("--llm", action="store_true", help="使用真实 LLM 解释协议边界")
    parser.add_argument("--request", help="发送一条 JSON-RPC 请求")
    parser.add_argument("--token", default="demo-token", help="本地 Demo token；不要放入真实凭证")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.llm:
        output = ask_llm("解释 MCP、A2A 和 ANP 分别解决什么通信问题，并说明认证、权限和任务生命周期为什么不能省略。")
    elif args.request:
        output = dispatch_request(args.request, token=args.token)
    else:
        output = run_demo() if args.demo else make_task()
    print(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm

from werewolf_arena.engine import GameEngine
from werewolf_arena.evaluation import evaluate_game
from werewolf_arena.policies import LLMPolicy, OpenAICompatibleModelAdapter
from werewolf_arena.schemas import Phase
from werewolf_arena.storage import ArtifactStore, RequestTraceStore


# 项目根目录同时是默认对局记录的落盘位置，而不是调用命令时的当前工作目录。
PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> None:
    """解析命令行、选择 Policy、运行或恢复游戏，并持久化本局工件。"""
    parser = argparse.ArgumentParser()
    # --demo 保留为与其他课程项目一致的离线入口；当前默认行为就是完整演示局。
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--policy", choices=("rule", "llm"), default="rule")
    parser.add_argument("--progress", action="store_true", help="将 LLM 请求进度写到 stderr")
    parser.add_argument("--spectate", action="store_true", help="输出不含私密信息的实时公开叙事")
    parser.add_argument("--god-view", action="store_true", help="生成仅供开发/裁判使用的完整审计页面")
    parser.add_argument("--interrupt-after-phase", choices=[phase.value for phase in Phase if phase != Phase.FINISHED])
    args = parser.parse_args()
    output_dir = args.output_dir or (
        args.resume.parent if args.resume else ArtifactStore.default_run_directory(PROJECT_ROOT, args.seed)
    )
    if args.llm:
        # 这是课程概念问答模式，不会把六名玩家切换到真实对局模型。
        print(ask_llm("给六 Agent 狼人杀毕业项目列出模型 Policy、规则引擎、评测与安全的检查清单。"))
        return
    # 默认使用离线规则策略；只有用户显式传入 --policy llm 才读取模型环境变量。
    policies = None
    on_public_event = None
    if args.spectate:
        output_stream = sys.stderr if args.json else sys.stdout

        def on_public_event(line: str) -> None:
            print(f"[观战] {line}", file=output_stream, flush=True)

    if args.policy == "llm":
        # 六个 Policy 拥有各自的 Observation/PROMPT，上层适配器统一负责网络调用。
        on_event = None
        if args.progress:
            def on_event(event: dict) -> None:
                details = " ".join(
                    f"{key}={event[key]}"
                    for key in ("attempt", "reason", "latency_ms")
                    if key in event
                )
                print(f"[llm] {event.get('event', 'event')} {details}".rstrip(), file=sys.stderr, flush=True)

        model = OpenAICompatibleModelAdapter.from_environment(on_event=on_event)
        request_trace = RequestTraceStore(output_dir / "llm_requests.jsonl")
        policies = {
            player_id: LLMPolicy(player_id, model, on_request=request_trace.append)
            for player_id in ("alice", "bob", "carol", "david", "eve", "frank")
        }

    # 新游戏默认写入项目内唯一 runs/<timestamp>-seed-<seed>-<id>/；
    # 恢复游戏则默认继续使用原 checkpoint 所在目录，避免产生分叉记录。
    if args.resume:
        # 恢复路径会保留已有 checkpoint；最终 ArtifactStore 仍会刷新报告和 JSONL。
        state = GameEngine.resume(
            args.resume,
            max_rounds=args.max_rounds,
            policies=policies,
            on_public_event=on_public_event,
        )
    else:
        state = GameEngine(seed=args.seed, policies=policies).run(
            max_rounds=args.max_rounds,
            interrupt_after_phase=Phase(args.interrupt_after_phase) if args.interrupt_after_phase else None,
            checkpoint_path=output_dir / "checkpoint.json",
            on_public_event=on_public_event,
        )
    # 一局结束后统一评测，再将状态、逐事件轨迹和摘要落盘。
    report = evaluate_game(state, offline=args.policy != "llm")
    artifacts = ArtifactStore(output_dir).write(state, report, god_view=args.god_view)
    payload = {"state": state.to_dict(), "report": report, "artifacts": artifacts}
    if args.json or not args.spectate:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=args.json))
    else:
        print(f"[观战] 页面已生成：{artifacts['spectator']}")


if __name__ == "__main__":
    # 仅直接执行此文件时启动 CLI；被测试或其他模块导入时不产生副作用。
    main()

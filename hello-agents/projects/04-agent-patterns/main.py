"""用确定性轨迹比较 ReAct、Plan-and-Solve 和 Reflection。"""

import argparse
from dataclasses import asdict, dataclass, field
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


@dataclass
class Environment:
    """供离线范式使用的极小检索环境。"""

    sources: dict[str, str] = field(
        default_factory=lambda: {
            "agent": "S1：Agent 由模型、工具和状态组成。",
            "runtime": "S2：Runtime 负责权限、步数、错误和终止。",
            "fallback": "S3：可靠系统需要记录 action、observation 和 error。",
        }
    )

    def search(self, topic: str) -> str:
        if topic not in self.sources:
            raise KeyError(f"没有可用来源: {topic}")
        return self.sources[topic]

    def invalidate(self, topic: str) -> None:
        self.sources.pop(topic, None)


@dataclass(frozen=True)
class TraceEvent:
    """只记录可审计的行动轨迹，不保存隐藏思考文本。"""

    step: int
    pattern: str
    phase: str
    action: str
    observation: str = ""
    error: str | None = None
    state: dict[str, Any] = field(default_factory=dict)


def _event(
    step: int,
    pattern: str,
    phase: str,
    action: str,
    *,
    observation: str = "",
    error: str | None = None,
    state: dict[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        step=step,
        pattern=pattern,
        phase=phase,
        action=action,
        observation=observation,
        error=error,
        state=dict(state or {}),
    )


def _safe_search(environment: Environment, topic: str) -> tuple[str, str | None]:
    try:
        return environment.search(topic), None
    except KeyError as exc:
        return "", str(exc)


def run_react(
    topics: list[str] | None = None,
    *,
    environment: Environment | None = None,
    max_steps: int = 6,
    repeat_action: bool = False,
) -> list[TraceEvent]:
    """执行观察→行动→反馈循环，并拒绝相邻重复行动。"""
    if max_steps < 1:
        raise ValueError("max_steps 必须大于 0")
    topics = list(topics or ["agent", "runtime"])
    environment = environment or Environment()
    pending = list(topics)
    observations: dict[str, str] = {}
    trace: list[TraceEvent] = []
    previous_action = ""

    for step in range(1, max_steps + 1):
        if pending:
            topic = pending[0]
            action = f"search:{topic}"
            if repeat_action and step == 2:
                action = previous_action
                topic = action.split(":", 1)[1]

            if action == previous_action:
                trace.append(
                    _event(
                        step,
                        "ReAct",
                        "guard",
                        action,
                        error="检测到重复行动，停止循环",
                        state={"pending": list(pending)},
                    )
                )
                return trace

            observation, error = _safe_search(environment, topic)
            trace.append(
                _event(
                    step,
                    "ReAct",
                    "act",
                    action,
                    observation=observation,
                    error=error,
                    state={"pending": list(pending)},
                )
            )
            previous_action = action
            if error:
                return trace
            observations[topic] = observation
            pending.pop(0)
            continue

        answer = "；".join(observations.values())
        trace.append(
            _event(
                step,
                "ReAct",
                "answer",
                "answer",
                observation=answer,
                state={"observations": list(observations)},
            )
        )
        return trace

    trace.append(
        _event(
            max_steps + 1,
            "ReAct",
            "guard",
            "terminate",
            error=f"超过最大步数 {max_steps}",
            state={"pending": list(pending)},
        )
    )
    return trace


def run_plan_and_solve(
    topics: list[str] | None = None,
    *,
    environment: Environment | None = None,
    max_steps: int = 8,
    invalidate_after: int | None = None,
) -> list[TraceEvent]:
    """先生成计划再执行；来源失效时记录重规划并切换备用来源。"""
    if max_steps < 1:
        raise ValueError("max_steps 必须大于 0")
    topics = list(topics or ["agent", "runtime"])
    environment = environment or Environment()
    plan = [f"search:{topic}" for topic in topics] + ["answer"]
    trace: list[TraceEvent] = [
        _event(
            1,
            "Plan-and-Solve",
            "plan",
            "create_plan",
            observation=str(plan),
            state={"plan": list(plan)},
        )
    ]
    observations: dict[str, str] = {}
    executed_searches = 0
    step = 2

    while plan and step <= max_steps:
        action = plan.pop(0)
        if action.startswith("search:"):
            topic = action.split(":", 1)[1]
            if invalidate_after is not None and executed_searches == invalidate_after:
                environment.invalidate(topic)
                remaining = list(plan)
                plan = ["search:fallback" if item == action else item for item in [action] + remaining]
                trace.append(
                    _event(
                        step,
                        "Plan-and-Solve",
                        "replan",
                        "replan",
                        observation=f"来源 {topic} 失效，改用 fallback",
                        error="原计划失效",
                        state={"plan": list(plan)},
                    )
                )
                step += 1
                if step > max_steps:
                    break
                action = plan.pop(0)
                topic = action.split(":", 1)[1]

            observation, error = _safe_search(environment, topic)
            trace.append(
                _event(
                    step,
                    "Plan-and-Solve",
                    "execute",
                    action,
                    observation=observation,
                    error=error,
                    state={"plan": list(plan)},
                )
            )
            if error:
                return trace
            observations[topic] = observation
            executed_searches += 1
        else:
            answer = "；".join(observations.values())
            trace.append(
                _event(
                    step,
                    "Plan-and-Solve",
                    "answer",
                    "answer",
                    observation=answer,
                    state={"observations": list(observations)},
                )
            )
            return trace
        step += 1

    trace.append(
        _event(
            step,
            "Plan-and-Solve",
            "guard",
            "terminate",
            error=f"超过最大步数 {max_steps}",
            state={"plan": list(plan)},
        )
    )
    return trace


def rule_check(
    answer: str,
    citations: list[str],
    available_sources: set[str],
) -> list[str]:
    """基于规则检查答案是否为空、是否包含未知引用。"""
    issues: list[str] = []
    if not answer.strip():
        issues.append("答案为空")
    unknown = sorted(set(citations) - available_sources)
    if unknown:
        issues.append(f"引用不存在: {', '.join(unknown)}")
    if not citations:
        issues.append("缺少引用")
    return issues


def run_reflection(
    *,
    answer: str = "Agent 需要模型、工具和状态。",
    citations: list[str] | None = None,
    available_sources: set[str] | None = None,
) -> list[TraceEvent]:
    """生成草稿，用规则检查质量，再修订引用。"""
    citations = list(citations or ["S1", "S-missing"])
    available_sources = set(available_sources or {"S1", "S2"})
    trace: list[TraceEvent] = [
        _event(
            1,
            "Reflection",
            "draft",
            "draft",
            observation=answer,
            state={"citations": list(citations)},
        )
    ]
    issues = rule_check(answer, citations, available_sources)
    trace.append(
        _event(
            2,
            "Reflection",
            "critique",
            "rule_check",
            observation="；".join(issues) if issues else "检查通过",
            error="；".join(issues) if issues else None,
            state={"citations": list(citations)},
        )
    )
    if issues:
        citations = [citation for citation in citations if citation in available_sources]
        revised = answer + "（已移除无法验证的引用）"
        trace.append(
            _event(
                3,
                "Reflection",
                "revise",
                "revise",
                observation=revised,
                state={"citations": list(citations)},
            )
        )
        answer = revised
    trace.append(
        _event(
            len(trace) + 1,
            "Reflection",
            "answer",
            "answer",
            observation=answer,
            state={"citations": list(citations)},
        )
    )
    return trace


def render_trace(trace: list[TraceEvent]) -> str:
    """把轨迹渲染成可读文本，避免输出隐藏思考内容。"""
    lines = []
    for event in trace:
        line = f"{event.step}. [{event.pattern}/{event.phase}] {event.action}"
        if event.observation:
            line += f" -> {event.observation}"
        if event.error:
            line += f" [error={event.error}]"
        lines.append(line)
    return "\n".join(lines)


def demo(
    *,
    invalidate_plan: bool = False,
    repeat_react: bool = False,
    bad_citation: bool = True,
    as_json: bool = False,
) -> str:
    """运行三种范式的离线轨迹比较。"""
    react = run_react(repeat_action=repeat_react)
    plan = run_plan_and_solve(invalidate_after=1 if invalidate_plan else None)
    reflection = run_reflection() if bad_citation else run_reflection(citations=["S1"])
    traces = {"ReAct": react, "Plan-and-Solve": plan, "Reflection": reflection}
    if as_json:
        return json.dumps(
            {name: [asdict(event) for event in trace] for name, trace in traces.items()},
            ensure_ascii=False,
            indent=2,
        )
    return "\n\n".join(
        f"{name}:\n{render_trace(trace)}" for name, trace in traces.items()
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--invalidate-plan", action="store_true")
    parser.add_argument("--repeat-react", action="store_true")
    parser.add_argument("--valid-citation", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.llm:
        output = ask_llm(
            "比较 ReAct、Plan-and-Solve、Reflection，说明状态流转、适用场景、"
            "重规划、循环检测和规则质量检查。"
        )
    else:
        output = demo(
            invalidate_plan=args.invalidate_plan,
            repeat_react=args.repeat_react,
            bad_citation=not args.valid_citation,
            as_json=args.json,
        )
    print(output)


if __name__ == "__main__":
    main()

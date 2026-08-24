"""本地确定性研究资料库。"""

from datetime import datetime, timedelta, timezone

from .schemas import Source


def fixture_sources(*, conflict: bool = False) -> tuple[Source, ...]:
    now = datetime(2026, 8, 24, 9, 0, tzinfo=timezone(timedelta(hours=8), name="CST"))
    sources = [
        Source(
            "S1",
            "Agent 状态架构记录",
            "https://local.test/agent-state",
            "Local Research Lab",
            "2026-01-10",
            "Agent 由模型、工具和状态组成，状态可以通过检查点保存。",
            0.95,
            now,
            "agent_state",
            "supports",
        ),
        Source(
            "S2",
            "离线评测记录",
            "https://local.test/offline-eval",
            "Evaluation Team",
            "2026-02-12",
            "离线数据集可以用于回归测试和发布前评估。",
            0.90,
            now,
            "offline_eval",
            "supports",
        ),
    ]
    if conflict:
        sources.append(
            Source(
                "S3",
                "反例研究记录",
                "https://local.test/state-counterexample",
                "Independent Reviewer",
                "2026-03-01",
                "反例显示某些 Agent 在没有持久化状态时也可以完成一次性任务。",
                0.70,
                now,
                "agent_state",
                "contradicts",
            )
        )
    return tuple(sources)

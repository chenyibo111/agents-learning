"""狼人杀轨迹的规则、隐私和成本评测。"""

import json
from collections import Counter
from typing import Any

from .schemas import GameState


def evaluate_game(state: GameState) -> dict[str, Any]:
    """把最终状态与事件轨迹汇总为胜负、规则、隐私和成本报告。"""
    counts = Counter(event.event_type for event in state.events)
    # 这些字段只应存在于私有状态或私有事件；出现在 public Event 中即视为泄露。
    forbidden = ("private_memory", "wolf_teammates", "inspection_results", "antidote_available", "poison_available", '"role"')
    leaks = []
    for event in state.events:
        # 只检查公开事件，完整 checkpoint 本身是受保护的审计数据而非玩家展示数据。
        if event.public:
            encoded = json.dumps(event.to_dict(), ensure_ascii=False)
            leaks.extend(item for item in forbidden if item in encoded)
    # report 保持 JSON 基础类型，便于 CLI、文件和未来 Web API 复用。
    return {
        "status": state.status,
        "winner": state.winner or "draw",
        "rounds": state.round_number,
        "event_count": len(state.events),
        "event_types": dict(sorted(counts.items())),
        "rejected_action_count": counts["action_rejected"],
        "speech_count": counts["speech"],
        "vote_count": counts["vote_cast"],
        "metrics": dict(state.metrics),
        "rule_compliance": {"passed": counts["action_rejected"] == 0},
        "privacy_audit": {"passed": not leaks, "leaks": sorted(set(leaks))},
        "offline": True,
    }

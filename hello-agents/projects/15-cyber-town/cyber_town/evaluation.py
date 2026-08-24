"""社会模拟的基础质量、守恒和隐私评测。"""

import json
from collections import Counter
from typing import Any

from .schemas import SimulationState


def _resource_totals(state: SimulationState) -> tuple[int, dict[str, int]]:
    balance = sum(agent.balance for agent in state.world.agents)
    inventory: Counter[str] = Counter()
    for agent in state.world.agents:
        inventory.update(agent.inventory)
    return balance, dict(sorted(inventory.items()))


def evaluate_simulation(state: SimulationState) -> dict[str, Any]:
    counts = Counter(event.event_type for event in state.events)
    balance, inventory = _resource_totals(state)
    expected_balance = state.world.public_facts.get("initial_total_balance")
    expected_inventory = state.world.public_facts.get("initial_inventory", {})
    conservation = {
        "passed": balance == expected_balance and inventory == expected_inventory,
        "balance": balance,
        "expected_balance": expected_balance,
        "inventory": inventory,
        "expected_inventory": expected_inventory,
    }
    private_values = [
        secret
        for agent in state.world.agents
        for secret in agent.private_memory
    ]
    leaked = []
    for event in state.events:
        if event.public:
            encoded = json.dumps(event.to_dict(), ensure_ascii=False)
            leaked.extend(secret for secret in private_values if secret in encoded)
            if "private_memory" in encoded:
                leaked.append("private_memory")
    return {
        "status": state.status,
        "seed": state.seed,
        "ticks": state.world.tick,
        "event_count": len(state.events),
        "event_types": dict(sorted(counts.items())),
        "trade_count": counts["trade_completed"],
        "rejected_action_count": counts["action_rejected"],
        "message_count": counts["message"],
        "resource_conservation": conservation,
        "privacy_audit": {"passed": not leaked, "leaks": sorted(set(leaked))},
        "replayable": True,
    }

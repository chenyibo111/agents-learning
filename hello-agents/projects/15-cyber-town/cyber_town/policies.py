"""可插拔 Policy：规则 NPC 与未来 LLM Policy 共用同一决策接口。"""

from typing import Protocol

from .schemas import Action, Observation


class Policy(Protocol):
    name: str

    def decide(self, observation: Observation) -> Action:
        ...


class MerchantPolicy:
    name = "rule-merchant"

    def decide(self, observation: Observation) -> Action:
        inventory = observation.own_state.get("inventory", {})
        if observation.tick == 0 and inventory.get("map", 0) >= 1:
            return Action("merchant", "offer", "researcher", "map", 1, 5)
        return Action("merchant", "message", message="商人检查了摊位。")


class ResearcherPolicy:
    name = "rule-researcher"

    def decide(self, observation: Observation) -> Action:
        for event in reversed(observation.visible_events):
            if event["tick"] != observation.tick or event["event_type"] != "offer":
                continue
            if event["target_id"] == "researcher":
                payload = event["payload"]
                return Action(
                    "researcher", "accept", event["actor_id"], payload["item"], payload["quantity"], payload["price"]
                )
        return Action("researcher", "message", message="研究员记录了今天的市场情况。")


class CourierPolicy:
    name = "rule-courier"

    def decide(self, observation: Observation) -> Action:
        if observation.tick == 0:
            return Action("courier", "message", message="信使：市场已经开张。")
        return Action("courier", "noop")


def default_policies() -> dict[str, Policy]:
    return {
        "merchant": MerchantPolicy(),
        "researcher": ResearcherPolicy(),
        "courier": CourierPolicy(),
    }

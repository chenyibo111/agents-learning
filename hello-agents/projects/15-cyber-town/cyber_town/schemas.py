"""赛博小镇的领域对象和可持久化 Schema。"""

from dataclasses import dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class AgentState:
    agent_id: str
    role: str
    goals: tuple[str, ...]
    balance: int
    inventory: dict[str, int]
    private_memory: tuple[str, ...]
    relationships: dict[str, int] = field(default_factory=dict)
    policy_name: str = "rule"

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "goals": list(self.goals),
            "balance": self.balance,
            "inventory": dict(sorted(self.inventory.items())),
            "private_memory": list(self.private_memory),
            "relationships": dict(sorted(self.relationships.items())),
            "policy_name": self.policy_name,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AgentState":
        return cls(
            agent_id=value["agent_id"],
            role=value["role"],
            goals=tuple(value.get("goals", [])),
            balance=value["balance"],
            inventory=dict(value.get("inventory", {})),
            private_memory=tuple(value.get("private_memory", [])),
            relationships=dict(value.get("relationships", {})),
            policy_name=value.get("policy_name", "rule"),
        )


@dataclass(frozen=True)
class WorldState:
    tick: int
    public_facts: dict[str, Any]
    market: dict[str, Any]
    agents: tuple[AgentState, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "public_facts": self.public_facts,
            "market": self.market,
            "agents": [agent.to_dict() for agent in self.agents],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WorldState":
        return cls(
            tick=value["tick"],
            public_facts=dict(value.get("public_facts", {})),
            market=dict(value.get("market", {})),
            agents=tuple(AgentState.from_dict(item) for item in value.get("agents", [])),
        )


@dataclass(frozen=True)
class Action:
    agent_id: str
    action_type: str
    target_id: str | None = None
    item: str | None = None
    quantity: int = 0
    price: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "target_id": self.target_id,
            "item": self.item,
            "quantity": self.quantity,
            "price": self.price,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Action":
        return cls(**value)


@dataclass(frozen=True)
class Event:
    event_id: str
    tick: int
    event_type: str
    actor_id: str
    target_id: str | None
    payload: dict[str, Any]
    public: bool = True
    rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "tick": self.tick,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "payload": self.payload,
            "public": self.public,
            "rule": self.rule,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Event":
        return cls(**value)


@dataclass(frozen=True)
class Observation:
    agent_id: str
    tick: int
    public_facts: dict[str, Any]
    market: dict[str, Any]
    own_state: dict[str, Any]
    visible_events: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "tick": self.tick,
            "public_facts": self.public_facts,
            "market": self.market,
            "own_state": self.own_state,
            "visible_events": list(self.visible_events),
        }


@dataclass(frozen=True)
class SimulationState:
    world: WorldState
    events: tuple[Event, ...]
    status: str
    seed: int
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "world": self.world.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "status": self.status,
            "seed": self.seed,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SimulationState":
        if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError("不支持的赛博小镇状态 schema 版本")
        return cls(
            world=WorldState.from_dict(value["world"]),
            events=tuple(Event.from_dict(item) for item in value.get("events", [])),
            status=value["status"],
            seed=value["seed"],
            schema_version=value.get("schema_version", SCHEMA_VERSION),
        )

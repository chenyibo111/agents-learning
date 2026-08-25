"""狼人杀毕业项目的版本化领域对象。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# 所有持久化 JSON 都携带版本号；未来字段变化时可拒绝错误版本，而不是静默读错。
SCHEMA_VERSION = "1.0"


class Role(str, Enum):
    """游戏引擎认可的四种真实身份；身份只存于服务端 GameState。"""
    WOLF = "wolf"
    SEER = "seer"
    WITCH = "witch"
    VILLAGER = "villager"


class Phase(str, Enum):
    """有限状态机的全部阶段，规则引擎只允许按既定顺序推进。"""
    NIGHT_WOLF = "night_wolf"
    NIGHT_SEER = "night_seer"
    NIGHT_WITCH = "night_witch"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    FINISHED = "finished"


@dataclass(frozen=True)
class PlayerState:
    """单个玩家的真实私有状态，不可直接交给其他玩家或模型。"""
    player_id: str
    role: Role
    alive: bool = True
    private_memory: tuple[str, ...] = ()
    antidote_available: bool = False
    poison_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        """将内部对象转换为可写入 checkpoint 的基础 JSON 数据。"""
        return {
            "player_id": self.player_id,
            "role": self.role.value,
            "alive": self.alive,
            "private_memory": list(self.private_memory),
            "antidote_available": self.antidote_available,
            "poison_available": self.poison_available,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlayerState":
        """从 checkpoint 重建玩家，并把字符串身份恢复为 Role 枚举。"""
        return cls(
            player_id=value["player_id"],
            role=Role(value["role"]),
            alive=value.get("alive", True),
            private_memory=tuple(value.get("private_memory", [])),
            antidote_available=value.get("antidote_available", False),
            poison_available=value.get("poison_available", False),
        )


@dataclass(frozen=True)
class Action:
    """Policy 提交给环境的意图；它尚未被接受，也不会直接改写游戏。"""
    actor_id: str
    action_type: str
    target_id: str | None = None
    speech: str = ""
    decision_label: str = ""
    model_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """序列化行动及关联的模型调用指标，供 checkpoint 和审计使用。"""
        return {
            "actor_id": self.actor_id,
            "action_type": self.action_type,
            "target_id": self.target_id,
            "speech": self.speech,
            "decision_label": self.decision_label,
            "model_calls": self.model_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Action":
        """从 JSON 恢复已经提交但尚未结算的行动。"""
        return cls(**value)


@dataclass(frozen=True)
class Event:
    """环境确认后的事实；public 和 recipients 决定它能被谁观察到。"""
    event_id: str
    round_number: int
    phase: Phase
    event_type: str
    payload: dict[str, Any]
    public: bool = True
    recipients: tuple[str, ...] = ()
    rule: str = ""

    def to_dict(self) -> dict[str, Any]:
        """把事件转换为 JSONL 的单条记录格式。"""
        return {
            "event_id": self.event_id,
            "round_number": self.round_number,
            "phase": self.phase.value,
            "event_type": self.event_type,
            "payload": self.payload,
            "public": self.public,
            "recipients": list(self.recipients),
            "rule": self.rule,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Event":
        """从 JSON 恢复事件，并把阶段字符串恢复为枚举。"""
        return cls(
            event_id=value["event_id"],
            round_number=value["round_number"],
            phase=Phase(value["phase"]),
            event_type=value["event_type"],
            payload=dict(value.get("payload", {})),
            public=value.get("public", True),
            recipients=tuple(value.get("recipients", [])),
            rule=value.get("rule", ""),
        )


@dataclass(frozen=True)
class PlayerObservation:
    """某位玩家被授权看到的最小视图，也是 Policy 的唯一输入。"""
    player_id: str
    phase: Phase
    round_number: int
    public: dict[str, Any]
    private: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """输出适合 Prompt、调试和测试断言的观察快照。"""
        return {
            "player_id": self.player_id,
            "phase": self.phase.value,
            "round_number": self.round_number,
            "public": self.public,
            "private": self.private,
        }


@dataclass(frozen=True)
class GameState:
    """引擎持有的完整上帝视角状态，包含身份、私有事件和待结算行动。"""
    game_id: str
    seed: int
    round_number: int
    phase: Phase
    players: tuple[PlayerState, ...]
    events: tuple[Event, ...] = ()
    pending_actions: tuple[Action, ...] = ()
    night_victim: str | None = None
    status: str = "RUNNING"
    winner: str | None = None
    metrics: dict[str, float | int] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """完整序列化一局游戏；调用方必须把该数据当作受保护审计工件。"""
        return {
            "game_id": self.game_id,
            "seed": self.seed,
            "round_number": self.round_number,
            "phase": self.phase.value,
            "players": [player.to_dict() for player in self.players],
            "events": [event.to_dict() for event in self.events],
            "pending_actions": [action.to_dict() for action in self.pending_actions],
            "night_victim": self.night_victim,
            "status": self.status,
            "winner": self.winner,
            "metrics": self.metrics,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GameState":
        """验证 schema 版本并从 checkpoint 恢复可继续运行的游戏状态。"""
        if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError("不支持的狼人杀状态 schema 版本")
        return cls(
            game_id=value["game_id"],
            seed=value["seed"],
            round_number=value["round_number"],
            phase=Phase(value["phase"]),
            players=tuple(PlayerState.from_dict(item) for item in value["players"]),
            events=tuple(Event.from_dict(item) for item in value.get("events", [])),
            pending_actions=tuple(Action.from_dict(item) for item in value.get("pending_actions", [])),
            night_victim=value.get("night_victim"),
            status=value.get("status", "RUNNING"),
            winner=value.get("winner"),
            metrics=dict(value.get("metrics", {})),
            schema_version=value.get("schema_version", SCHEMA_VERSION),
        )

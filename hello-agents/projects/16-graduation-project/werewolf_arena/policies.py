"""离线规则 Agent 与可替换模型 Policy。"""

from dataclasses import dataclass
import json
import os
from typing import Protocol
from urllib import request

from .schemas import Action, Phase, PlayerObservation, Role
from .visibility import model_prompts


@dataclass(frozen=True)
class ModelResponse:
    """模型适配器返回的文本与可计量成本；不保存任何密钥或原始 HTTP 请求。"""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class ModelAdapter(Protocol):
    """统一模型边界，便于在规则、脚本和真实模型间替换。"""
    def complete(self, system_prompt: str, user_prompt: str) -> ModelResponse:
        """接收已隔离的 Prompt，并返回文本与本次调用的可计量指标。"""
        ...


class LLMConfigurationError(RuntimeError):
    """真实模型适配器缺少环境配置时抛出，且不回显密钥。"""


class OpenAICompatibleModelAdapter:
    """可选的 OpenAI Chat Completions 兼容适配器，默认不会被创建。"""

    def __init__(self, endpoint: str, api_key: str, model: str, timeout_seconds: int = 30):
        """保存显式配置；缺失任一项时拒绝启动且不回显 secret。"""
        if not endpoint or not api_key or not model:
            raise LLMConfigurationError("真实模型需要 WEREWOLF_LLM_ENDPOINT、WEREWOLF_LLM_API_KEY 和 WEREWOLF_LLM_MODEL")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleModelAdapter":
        """只从环境读取模型配置，避免把 endpoint 或 API key 写入代码和记录。"""
        return cls(
            endpoint=os.environ.get("WEREWOLF_LLM_ENDPOINT", ""),
            api_key=os.environ.get("WEREWOLF_LLM_API_KEY", ""),
            model=os.environ.get("WEREWOLF_LLM_MODEL", ""),
        )

    def complete(self, system_prompt: str, user_prompt: str) -> ModelResponse:
        """按 OpenAI Chat Completions 兼容格式请求 JSON，并提取用量指标。"""
        # response_format 要求服务端产出对象；本地 LLMPolicy 仍会二次解析并兜底。
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": 0.4,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        # endpoint 只能由部署者配置；默认离线模式不会创建此适配器或发出网络请求。
        http_request = request.Request(
            self.endpoint,
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:  # noqa: S310 - endpoint is explicit user configuration
            value = json.loads(response.read().decode("utf-8"))
        # 兼容部分供应商返回的多段 content 数组与常见的单字符串 content。
        content = value["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        usage = value.get("usage", {})
        return ModelResponse(
            text=str(content),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


class Policy(Protocol):
    """所有玩家决策器都必须遵循的最小接口。"""
    def decide(self, observation: PlayerObservation) -> Action:
        """基于单个玩家的授权视图提出一个结构化 Action。"""
        ...


class ScriptedModelAdapter:
    """测试和离线演示使用的模型替身；不会访问网络。"""

    def __init__(self, responses: list[str] | tuple[str, ...]):
        """接收预排响应，供测试正常、错误和边界模型输出。"""
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> ModelResponse:
        """记录本次 Prompt 后返回下一条脚本响应；耗尽时安全返回 noop JSON。"""
        self.calls.append((system_prompt, user_prompt))
        text = self.responses.pop(0) if self.responses else '{"action_type": "noop"}'
        return ModelResponse(text=text, input_tokens=len(user_prompt) // 4, output_tokens=len(text) // 4)


class LLMPolicy:
    """仅将授权 Observation 交给模型；无效输出会回退到 noop。"""

    def __init__(self, player_id: str, model: ModelAdapter):
        """绑定一个玩家 ID 与模型边界；模型无法伪造另一个 actor_id。"""
        self.player_id = player_id
        self.model = model

    def decide(self, observation: PlayerObservation) -> Action:
        """把授权 Observation 转换成模型输入，解析 JSON 并在失败时降级为 noop。"""
        system_prompt, user_prompt = model_prompts(observation)
        response = self.model.complete(system_prompt, user_prompt)
        # actor_id 始终由服务端 Policy 固定，绝不信任模型输出中的玩家身份。
        base = {
            "actor_id": self.player_id,
            "model_calls": 1,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
        }
        try:
            value = json.loads(response.text)
            if not isinstance(value, dict):
                raise ValueError("模型输出不是对象")
            # 这里只做格式解析；行动在 rules.submit_action 中再次做角色、阶段和目标校验。
            return Action(
                action_type=str(value.get("action_type", "noop")),
                target_id=value.get("target_id"),
                speech=str(value.get("speech", "")),
                decision_label=str(value.get("decision_label", "")),
                **base,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            # 模型格式错误不会让一局游戏崩溃，也不能变成未受控的自然语言行动。
            return Action(action_type="noop", decision_label="invalid_model_output", **base)


class RulePolicy:
    """可重复的离线 NPC，用来验证不依赖模型的完整游戏流程。"""

    def __init__(self, player_id: str):
        """为指定玩家创建确定性离线策略，用于可重复测试和无模型演示。"""
        self.player_id = player_id

    def decide(self, observation: PlayerObservation) -> Action:
        """根据当前阶段选择一个简单、稳定且合法的默认行动。"""
        alive = list(observation.public["alive_players"])
        private = observation.private
        role = private["role"]
        if observation.phase == Phase.NIGHT_WOLF:
            # 两只狼使用相同的“第一个非狼人”规则，确保离线演示会形成协同攻击。
            team = {self.player_id, *private.get("wolf_teammates", [])}
            target = next((player for player in alive if player not in team), None)
            return Action(self.player_id, "wolf_kill", target, decision_label="shared_wolf_target")
        if observation.phase == Phase.NIGHT_SEER:
            # 预言家优先查验未查过的存活玩家，避免重复查验浪费回合。
            inspected = {item["target"] for item in private.get("inspection_results", [])}
            target = next((player for player in alive if player != self.player_id and player not in inspected), None)
            return Action(self.player_id, "inspect", target, decision_label="inspect_unknown")
        if observation.phase == Phase.NIGHT_WITCH:
            # 演示策略优先救人；真实 LLM 可按胜率和身份推理决定是否保留药物。
            victim = private.get("night_victim")
            if victim and private.get("antidote_available"):
                return Action(self.player_id, "witch_save", victim, decision_label="save_night_victim")
            return Action(self.player_id, "noop", decision_label="preserve_potions")
        if observation.phase == Phase.DAY_DISCUSSION:
            # 固定发言保证离线流程可完整走通，不代表成熟的推理或欺骗策略。
            return Action(self.player_id, "speak", speech="我会根据公开事件和投票记录判断。", decision_label="public_reasoning")
        if observation.phase == Phase.DAY_VOTE:
            # 狼人避开队友投票；好人按稳定顺序投票，方便回归测试复现。
            if role == Role.WOLF.value:
                team = {self.player_id, *private.get("wolf_teammates", [])}
                target = next((player for player in alive if player not in team), None)
            else:
                target = next((player for player in alive if player != self.player_id), None)
            return Action(self.player_id, "vote" if target else "abstain", target, decision_label="deterministic_vote")
        return Action(self.player_id, "noop")

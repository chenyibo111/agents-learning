"""离线规则 Agent 与可替换模型 Policy。"""

from dataclasses import dataclass
import json
import hashlib
import os
import socket
import time
from typing import Any, Callable, Protocol
from urllib import error as urlerror
from urllib import request
from uuid import uuid4

from .schemas import Action, Phase, PlayerObservation, Role
from .visibility import model_prompts


ACTION_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["action_type"],
    "properties": {
        "action_type": {"type": "string"},
        "target_id": {"type": ["string", "null"]},
        "speech": {"type": "string", "maxLength": 240},
        "decision_label": {"type": ["string", "null"], "maxLength": 80},
    },
    "additionalProperties": False,
}

ACTION_ALIASES = {
    "kill": "wolf_kill",
    "wolf_attack": "wolf_kill",
    "night_kill": "wolf_kill",
    "confirm_kill": "wolf_vote",
    "wolf_confirm": "wolf_vote",
    "wolf_target_vote": "wolf_vote",
    "night_seer": "inspect",
    "seer_check": "inspect",
    "check": "inspect",
    "no_action": "noop",
    "none": "noop",
    "skip": "noop",
    "speech": "speak",
    "discuss": "speak",
    "discussion": "speak",
    "cast_vote": "vote",
    "vote_cast": "vote",
    "pass_vote": "abstain",
    "save": "witch_save",
    "poison": "witch_poison",
}

PHASE_ACTION_TYPES = {
    Phase.NIGHT_WOLF: {"wolf_speak", "noop"},
    Phase.NIGHT_WOLF_CONFIRM: {"wolf_vote", "noop"},
    Phase.NIGHT_SEER: {"inspect", "noop"},
    Phase.NIGHT_WITCH: {"witch_save", "witch_poison", "noop"},
    Phase.DAY_DISCUSSION: {"speak", "noop"},
    Phase.DAY_VOTE: {"vote", "abstain", "noop"},
}


@dataclass(frozen=True)
class ModelResponse:
    """模型适配器返回的文本与可计量成本；不保存任何密钥或原始 HTTP 请求。"""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    attempts: int = 1
    retry_count: int = 0
    failure_reason: str = ""


class ModelAdapter(Protocol):
    """统一模型边界，便于在规则、脚本和真实模型间替换。"""
    def complete(self, system_prompt: str, user_prompt: str) -> ModelResponse:
        """接收已隔离的 Prompt，并返回文本与本次调用的可计量指标。"""
        ...


ProgressCallback = Callable[[dict[str, Any]], None]
RequestTraceCallback = Callable[[dict[str, Any]], None]


class LLMConfigurationError(RuntimeError):
    """真实模型适配器缺少环境配置时抛出，且不回显密钥。"""


class SchemaValidationError(ValueError):
    """只携带稳定分类码的本地行动协议错误，不保存异常原文。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OpenAICompatibleModelAdapter:
    """可选的 OpenAI Chat Completions 兼容适配器，默认不会被创建。"""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 30,
        max_retries: int = 1,
        retry_backoff_seconds: float = 0.5,
        on_event: ProgressCallback | None = None,
        input_price_per_million: float = 0.0,
        output_price_per_million: float = 0.0,
        max_output_tokens: int = 2048,
        thinking: str = "disabled",
    ):
        """保存显式配置；缺失任一项时拒绝启动且不回显 secret。"""
        if not endpoint or not api_key or not model:
            raise LLMConfigurationError("真实模型需要 WEREWOLF_LLM_ENDPOINT、WEREWOLF_LLM_API_KEY 和 WEREWOLF_LLM_MODEL")
        if timeout_seconds <= 0:
            raise LLMConfigurationError("WEREWOLF_LLM_TIMEOUT_SECONDS 必须大于 0")
        if max_retries < 0:
            raise LLMConfigurationError("WEREWOLF_LLM_MAX_RETRIES 不能小于 0")
        if retry_backoff_seconds < 0:
            raise LLMConfigurationError("WEREWOLF_LLM_RETRY_BACKOFF_SECONDS 不能小于 0")
        if input_price_per_million < 0 or output_price_per_million < 0:
            raise LLMConfigurationError("模型 Token 价格不能小于 0")
        if max_output_tokens <= 0:
            raise LLMConfigurationError("WEREWOLF_LLM_MAX_OUTPUT_TOKENS 必须大于 0")
        if thinking not in {"auto", "enabled", "disabled"}:
            raise LLMConfigurationError("WEREWOLF_LLM_THINKING 必须是 auto、enabled 或 disabled")
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.on_event = on_event
        self.input_price_per_million = input_price_per_million
        self.output_price_per_million = output_price_per_million
        self.max_output_tokens = max_output_tokens
        self.thinking = thinking

    @classmethod
    def from_environment(cls, *, on_event: ProgressCallback | None = None) -> "OpenAICompatibleModelAdapter":
        """只从环境读取模型配置，避免把 endpoint 或 API key 写入代码和记录。"""
        return cls(
            endpoint=os.environ.get("WEREWOLF_LLM_ENDPOINT", ""),
            api_key=os.environ.get("WEREWOLF_LLM_API_KEY", ""),
            model=os.environ.get("WEREWOLF_LLM_MODEL", ""),
            timeout_seconds=_environment_float("WEREWOLF_LLM_TIMEOUT_SECONDS", 30.0),
            max_retries=_environment_int("WEREWOLF_LLM_MAX_RETRIES", 1),
            retry_backoff_seconds=_environment_float("WEREWOLF_LLM_RETRY_BACKOFF_SECONDS", 0.5),
            on_event=on_event,
            input_price_per_million=_environment_float("WEREWOLF_LLM_INPUT_PRICE_PER_MILLION", 0.0),
            output_price_per_million=_environment_float("WEREWOLF_LLM_OUTPUT_PRICE_PER_MILLION", 0.0),
            max_output_tokens=_environment_int("WEREWOLF_LLM_MAX_OUTPUT_TOKENS", 2048),
            thinking=os.environ.get("WEREWOLF_LLM_THINKING", "disabled").strip().lower(),
        )

    def complete(self, system_prompt: str, user_prompt: str) -> ModelResponse:
        """按 OpenAI Chat Completions 兼容格式请求 JSON，并提取用量指标。"""
        # response_format 要求服务端产出对象；本地 LLMPolicy 仍会二次解析并兜底。
        request_payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": self.max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        # auto 不发送供应商专属字段，disabled/enabled 则显式控制 DeepSeek 兼容网关的思考模式。
        if self.thinking != "auto":
            request_payload["thinking"] = {"type": self.thinking}
        payload = json.dumps(request_payload).encode("utf-8")
        # endpoint 只能由部署者配置；默认离线模式不会创建此适配器或发出网络请求。
        http_request = request.Request(
            self.endpoint,
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        started_at = time.monotonic()
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            self._emit({"event": "request_started", "attempt": attempt})
            try:
                with request.urlopen(http_request, timeout=self.timeout_seconds) as response:  # noqa: S310 - endpoint is explicit user configuration
                    value = json.loads(response.read().decode("utf-8"))
                # 兼容部分供应商返回的多段 content 数组与常见的单字符串 content。
                content = value["choices"][0]["message"]["content"]
                if isinstance(content, list):
                    content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
                usage = value.get("usage", {})
                latency_ms = _elapsed_ms(started_at)
                self._emit({"event": "request_succeeded", "attempt": attempt, "latency_ms": latency_ms})
                return ModelResponse(
                    text=str(content),
                    input_tokens=int(usage.get("prompt_tokens", 0)),
                    output_tokens=int(usage.get("completion_tokens", 0)),
                    cost_usd=_calculate_cost(
                        int(usage.get("prompt_tokens", 0)),
                        int(usage.get("completion_tokens", 0)),
                        self.input_price_per_million,
                        self.output_price_per_million,
                    ),
                    latency_ms=latency_ms,
                    attempts=attempt,
                    retry_count=attempt - 1,
                )
            except (TimeoutError, socket.timeout, urlerror.HTTPError, urlerror.URLError, OSError) as error:
                reason = _failure_reason(error)
                retryable = _is_retryable(error)
                if retryable and attempt < total_attempts:
                    self._emit({"event": "request_retrying", "attempt": attempt, "reason": reason})
                    delay = self.retry_backoff_seconds * (2 ** (attempt - 1))
                    if delay:
                        time.sleep(delay)
                    continue
                latency_ms = _elapsed_ms(started_at)
                self._emit({"event": "request_failed", "attempt": attempt, "reason": reason, "latency_ms": latency_ms})
                return ModelResponse(
                    text="",
                    latency_ms=latency_ms,
                    attempts=attempt,
                    retry_count=attempt - 1,
                    failure_reason=reason,
                )
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                # Provider 返回格式错误不是网络瞬时错误；重试没有确定收益，直接安全降级。
                latency_ms = _elapsed_ms(started_at)
                self._emit({"event": "request_failed", "attempt": attempt, "reason": "invalid_provider_response", "latency_ms": latency_ms})
                return ModelResponse(
                    text="",
                    latency_ms=latency_ms,
                    attempts=attempt,
                    retry_count=attempt - 1,
                    failure_reason="invalid_provider_response",
                )

    def _emit(self, event: dict[str, Any]) -> None:
        """进度回调只能收到非敏感元数据；回调异常不能破坏模型调用。"""
        if self.on_event is None:
            return
        try:
            self.on_event(dict(event))
        except Exception:
            pass


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

    def __init__(self, player_id: str, model: ModelAdapter, on_request: RequestTraceCallback | None = None):
        """绑定一个玩家 ID 与模型边界；模型无法伪造另一个 actor_id。"""
        self.player_id = player_id
        self.model = model
        self.on_request = on_request

    def decide(self, observation: PlayerObservation) -> Action:
        """把授权 Observation 转换成模型输入，解析 JSON 并在失败时降级为 noop。"""
        system_prompt, user_prompt = model_prompts(observation)
        request_id = f"req-{uuid4().hex}"
        prompt_sha256 = _sha256_text(f"{system_prompt}\n{user_prompt}")
        response = self._complete(system_prompt, user_prompt)
        repair_attempted = False
        repair_reason = ""
        repair_succeeded = False
        schema_error_code = ""
        repair_schema_error_code = ""
        if response.failure_reason:
            # 适配器已经完成有限重试；规则层看到 noop，游戏仍可继续并在 decision_label 中保留原因。
            action = self._fallback_action(
                response,
                response.failure_reason,
                decision_label=f"llm_{response.failure_reason}",
            )
            self._emit_request_trace(request_id, observation, response, action, prompt_sha256)
            return action
        action, failure_reason, schema_error_code = _parse_model_action(response, observation, self.player_id)
        if action is not None:
            self._emit_request_trace(request_id, observation, response, action, prompt_sha256)
            return action

        # 仅对模型格式/Schema 错误做一次修复请求；网络、认证和供应商错误不重复请求。
        repair_attempted = True
        repair_reason = failure_reason
        repair_response = self._complete(system_prompt, _repair_user_prompt(user_prompt, failure_reason))
        response = _combine_model_responses(response, repair_response)
        if repair_response.failure_reason:
            action = self._fallback_action(
                response,
                repair_response.failure_reason,
                decision_label=f"llm_{repair_response.failure_reason}",
            )
        else:
            action, repair_failure_reason, repair_schema_error_code = _parse_model_action(
                response, observation, self.player_id
            )
            if action is None:
                action = self._fallback_action(response, repair_failure_reason or failure_reason)
            else:
                repair_succeeded = True
        self._emit_request_trace(
            request_id,
            observation,
            response,
            action,
            prompt_sha256,
            repair_attempted=repair_attempted,
            repair_reason=repair_reason,
            repair_succeeded=repair_succeeded,
            schema_error_code=schema_error_code,
            repair_schema_error_code=repair_schema_error_code,
        )
        return action

    def _complete(self, system_prompt: str, user_prompt: str) -> ModelResponse:
        """把自定义适配器异常转换为安全失败，不把异常文本暴露给游戏状态。"""
        try:
            return self.model.complete(system_prompt, user_prompt)
        except Exception:
            return ModelResponse(text="", failure_reason="adapter_error")

    def _fallback_action(
        self,
        response: ModelResponse,
        fallback_reason: str,
        *,
        decision_label: str = "invalid_model_output",
    ) -> Action:
        """用已经合并的模型指标创建安全 noop。"""
        return Action(
            actor_id=self.player_id,
            action_type="noop",
            decision_label=decision_label,
            fallback_reason=fallback_reason,
            model_calls=response.attempts,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
        )

    def _emit_request_trace(
        self,
        request_id: str,
        observation: PlayerObservation,
        response: ModelResponse,
        action: Action,
        prompt_sha256: str,
        *,
        repair_attempted: bool = False,
        repair_reason: str = "",
        repair_succeeded: bool = False,
        schema_error_code: str = "",
        repair_schema_error_code: str = "",
    ) -> None:
        """只发送可审计的脱敏摘要，不发送 Prompt、完整响应或密钥。"""
        if self.on_request is None:
            return
        record = {
            "request_id": request_id,
            "agent_id": self.player_id,
            "round": observation.round_number,
            "phase": observation.phase.value,
            "attempts": response.attempts,
            "retry_count": response.retry_count,
            "request_status": "failed" if response.failure_reason else "succeeded",
            "decision_status": "degraded" if action.fallback_reason else "parsed",
            "failure_reason": response.failure_reason or None,
            "fallback_reason": action.fallback_reason or None,
            "parsed_action_type": action.action_type,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "prompt_sha256": prompt_sha256,
            "response_sha256": _sha256_text(response.text) if response.text else None,
            "repair_attempted": repair_attempted,
            "repair_reason": repair_reason or None,
            "repair_succeeded": repair_succeeded,
            "schema_error_code": schema_error_code or None,
            "repair_schema_error_code": repair_schema_error_code or None,
        }
        try:
            self.on_request(dict(record))
        except Exception:
            # 追踪写入故障不能改变游戏决策和安全边界。
            pass


def _parse_model_action(
    response: ModelResponse,
    observation: PlayerObservation,
    actor_id: str,
) -> tuple[Action | None, str, str]:
    """解析一次模型响应；返回 Action、通用原因和稳定分类码。"""
    metrics = {
        "actor_id": actor_id,
        "model_calls": response.attempts,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost_usd": response.cost_usd,
        "latency_ms": response.latency_ms,
    }
    try:
        value = json.loads(response.text)
        normalized_action_type = _normalize_action_type(value, observation.phase)
        _validate_model_action(value, normalized_action_type, observation)
        # 这里只做格式解析；行动在 rules.submit_action 中再次做角色、阶段和目标校验。
        return (
            Action(
                action_type=normalized_action_type,
                target_id=value.get("target_id"),
                speech=str(value.get("speech", "")),
                decision_label=_normalize_decision_label(value.get("decision_label")),
                **metrics,
            ),
            "",
            "",
        )
    except json.JSONDecodeError:
        return None, "invalid_json", "invalid_json"
    except SchemaValidationError as error:
        return None, "schema_validation", error.code
    except (TypeError, ValueError):
        return None, "schema_validation", "schema_validation_error"


def _repair_user_prompt(user_prompt: str, failure_reason: str) -> str:
    """在不回显原始响应的前提下，要求模型基于同一视图重新生成结构化行动。"""
    reason = "JSON 无法解析" if failure_reason == "invalid_json" else "JSON 不符合行动 Schema"
    return (
        f"{user_prompt}\n\n"
        f"上一条输出存在问题：{reason}。请基于同一玩家视图重新生成。"
        "只返回一个 JSON 对象，不要 Markdown、解释、代码围栏或 reasoning。"
    )


def _combine_model_responses(first: ModelResponse, second: ModelResponse) -> ModelResponse:
    """合并首次请求和格式修复请求的计量指标，最终文本采用第二次响应。"""
    return ModelResponse(
        text=second.text,
        input_tokens=first.input_tokens + second.input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        cost_usd=round(first.cost_usd + second.cost_usd, 8),
        latency_ms=first.latency_ms + second.latency_ms,
        attempts=first.attempts + second.attempts,
        retry_count=first.retry_count + second.retry_count,
        failure_reason=second.failure_reason,
    )


def _normalize_action_type(value: Any, phase: Phase) -> str:
    """将模型常见别名归一化，并拒绝非字符串行动类型。"""
    if not isinstance(value, dict):
        raise SchemaValidationError("not_json_object")
    if "action_type" not in value:
        raise SchemaValidationError("missing_action_type")
    if not isinstance(value.get("action_type"), str):
        raise SchemaValidationError("action_type_type")
    action_type = value["action_type"].strip().lower()
    if not action_type:
        raise SchemaValidationError("action_type_empty")
    return ACTION_ALIASES.get(action_type, action_type)


def _validate_model_action(value: Any, action_type: str, observation: PlayerObservation) -> None:
    """执行不依赖第三方包的 JSON Schema 子集和阶段行动校验。"""
    phase = observation.phase
    if not isinstance(value, dict):
        raise SchemaValidationError("not_json_object")
    allowed_fields = set(ACTION_RESPONSE_SCHEMA["properties"])
    if set(value) - allowed_fields:
        raise SchemaValidationError("unknown_field")
    if "action_type" not in value:
        raise SchemaValidationError("missing_action_type")
    if not isinstance(value["action_type"], str):
        raise SchemaValidationError("action_type_type")
    if value.get("target_id") is not None and not isinstance(value["target_id"], str):
        raise SchemaValidationError("target_id_type")
    if not isinstance(value.get("speech", ""), str):
        raise SchemaValidationError("speech_type")
    if len(value.get("speech", "")) > 240:
        raise SchemaValidationError("speech_too_long")
    decision_label = value.get("decision_label")
    if isinstance(decision_label, str) and len(decision_label) > 80:
        raise SchemaValidationError("decision_label_too_long")
    if action_type not in PHASE_ACTION_TYPES.get(phase, {"noop"}):
        raise SchemaValidationError("phase_action_type")
    target_id = value.get("target_id")
    alive_players = set(observation.public.get("alive_players", ()))
    if phase == Phase.NIGHT_WOLF and action_type == "wolf_speak":
        if target_id is not None:
            raise SchemaValidationError("non_speech_target_not_null")
    elif phase == Phase.NIGHT_WOLF_CONFIRM and action_type == "wolf_vote":
        if not isinstance(target_id, str) or not target_id.strip():
            raise SchemaValidationError("wolf_vote_target_missing")
        if target_id not in alive_players:
            raise SchemaValidationError("wolf_vote_target_not_alive")
        if target_id == observation.player_id:
            raise SchemaValidationError("wolf_vote_self_target")
        if target_id in set(observation.private.get("wolf_teammates", ())):
            raise SchemaValidationError("wolf_vote_target_is_wolf")
    elif phase == Phase.NIGHT_SEER and action_type == "inspect":
        if not isinstance(target_id, str) or not target_id.strip():
            raise SchemaValidationError("inspect_target_missing")
        if target_id not in alive_players:
            raise SchemaValidationError("inspect_target_not_alive")
        if target_id == observation.player_id:
            raise SchemaValidationError("inspect_self_target")
    elif phase == Phase.NIGHT_WITCH and action_type == "witch_save":
        night_victim = observation.private.get("night_victim")
        if night_victim is None:
            raise SchemaValidationError("no_attack_to_save")
        if target_id != night_victim:
            raise SchemaValidationError("save_target_mismatch")
    elif phase == Phase.NIGHT_WITCH and action_type == "witch_poison":
        if not isinstance(target_id, str) or not target_id.strip():
            raise SchemaValidationError("poison_target_missing")
        if target_id not in alive_players:
            raise SchemaValidationError("poison_target_not_alive")
        if target_id == observation.player_id:
            raise SchemaValidationError("poison_self_target")
    if phase == Phase.DAY_VOTE:
        if action_type == "vote":
            if not isinstance(target_id, str) or not target_id.strip():
                raise SchemaValidationError("vote_target_missing")
            if target_id not in observation.public.get("alive_players", ()):
                raise SchemaValidationError("vote_target_not_alive")
            if target_id == observation.player_id:
                raise SchemaValidationError("vote_self_target")
        elif target_id is not None:
            raise SchemaValidationError("non_vote_target_not_null")


def _normalize_decision_label(value: Any) -> str:
    """将非关键决策标签规范为字符串；缺失、null 或其他类型统一为空。"""
    return value if isinstance(value, str) else ""


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
            # 协商阶段先提交一条私密建议，确认目标留到下一阶段。
            return Action(
                self.player_id,
                "wolf_speak",
                speech="我建议先观察公开票型，再统一确认目标。",
                decision_label="private_wolf_talk",
            )
        if observation.phase == Phase.NIGHT_WOLF_CONFIRM:
            # 两只狼使用相同的“第一个非狼人”规则，确保离线演示会形成协同攻击。
            team = {self.player_id, *private.get("wolf_teammates", [])}
            target = next((player for player in alive if player not in team), None)
            return Action(self.player_id, "wolf_vote", target, decision_label="shared_wolf_confirmation")
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


def _environment_int(name: str, default: int) -> int:
    value = os.environ.get(name, str(default))
    try:
        parsed = int(value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} 必须是整数") from error
    return parsed


def _environment_float(name: str, default: float) -> float:
    value = os.environ.get(name, str(default))
    try:
        return float(value)
    except ValueError as error:
        raise LLMConfigurationError(f"{name} 必须是数字") from error


def _elapsed_ms(started_at: float) -> int:
    return int(round((time.monotonic() - started_at) * 1000))


def _calculate_cost(input_tokens: int, output_tokens: int, input_price: float, output_price: float) -> float:
    """按每百万 Token 价格计算本次请求费用。"""
    return round((input_tokens * input_price + output_tokens * output_price) / 1_000_000, 8)


def _sha256_text(value: str) -> str:
    """只保存文本摘要，避免将 Prompt 或响应原文写入运行记录。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_reason(error: BaseException) -> str:
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(error, urlerror.HTTPError):
        return f"http_{error.code}"
    if isinstance(error, urlerror.URLError):
        return "network_error"
    if isinstance(error, OSError):
        return "network_error"
    return "provider_error"


def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, (TimeoutError, socket.timeout, urlerror.URLError, OSError)):
        if isinstance(error, urlerror.HTTPError):
            return error.code in {408, 425, 429} or 500 <= error.code <= 599
        return True
    return False

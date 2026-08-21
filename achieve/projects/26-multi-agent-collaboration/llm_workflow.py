"""Lesson 26: real LLM-backed specialist Agents coordinated by LangGraph."""

import json
import operator
import re
from typing import Annotated, Any, TypedDict

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    try:
        from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
    except ImportError:
        InMemorySaver = None  # type: ignore[assignment,misc]

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    LANGGRAPH_AVAILABLE = InMemorySaver is not None
except ImportError:
    END = START = StateGraph = Send = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False


ALLOWED_ROLES = ("researcher", "critic", "fact_checker")
DEFAULT_ROLES = ["researcher", "critic"]

ROLE_INSTRUCTIONS = {
    "researcher": (
        "你是研究员。提取与任务相关的事实、假设和可验证方向。"
        "不要声称自己访问了没有提供的外部资料。"
    ),
    "critic": (
        "你是审查员。寻找证据缺口、逻辑漏洞、成本、延迟、安全和失败风险。"
        "不要为了反对而反对，要给出可执行的改进建议。"
    ),
    "fact_checker": (
        "你是事实核验员。检查关键结论是否需要独立来源支持，标记不确定内容，"
        "并指出哪些结论不能仅凭当前上下文确认。"
    ),
}


class LLMState(TypedDict, total=False):
    task: str
    requested_roles: list[str]
    worker_results: Annotated[list[dict[str, Any]], operator.add]
    failures: Annotated[list[dict[str, str]], operator.add]
    events: Annotated[list[str], operator.add]
    final_answer: str
    status: str


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "本课需要 LangGraph，请先运行："
            "python -m pip install -r projects/26-multi-agent-collaboration/requirements.txt"
        )


def extract_response_text(response: Any) -> str:
    """Read text from an OpenAI SDK response or a test double."""
    if isinstance(response, dict):
        choices = response.get("choices", [])
        message = choices[0].get("message", {}) if choices else {}
        return str(message.get("content") or "")

    choices = getattr(response, "choices", [])
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    return str(getattr(message, "content", "") or "")


def parse_roles(content: str) -> list[str]:
    """Parse and whitelist the coordinator's role selection."""
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()

    candidates: Any = None
    try:
        candidates = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            try:
                candidates = json.loads(match.group(0))
            except json.JSONDecodeError:
                candidates = None

    if isinstance(candidates, dict):
        candidates = candidates.get("roles")
    if not isinstance(candidates, list):
        return DEFAULT_ROLES.copy()

    roles: list[str] = []
    for candidate in candidates:
        role = str(candidate).strip().lower()
        if role in ALLOWED_ROLES and role not in roles:
            roles.append(role)
    return roles or DEFAULT_ROLES.copy()


class LLMCollaborationRuntime:
    """Own the model client while LangGraph owns orchestration and state."""

    def __init__(self, client: Any, model: str) -> None:
        if not model:
            raise ValueError("model 不能为空")
        self.client = client
        self.model = model

    def call_model(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        content = extract_response_text(response)
        if not content:
            raise RuntimeError("模型没有返回文本内容")
        return content

    def coordinator(self, state: LLMState) -> dict[str, Any]:
        raw_roles = self.call_model(
            (
                "你是多 Agent 协调者。只能从 researcher、critic、fact_checker 中选择角色。"
                "根据任务决定需要哪些角色。至少选择 researcher 和 critic。"
                "只返回 JSON 数组，例如 [\"researcher\", \"critic\"]。"
            ),
            f"任务：{state['task']}",
        )
        roles = parse_roles(raw_roles)
        if "researcher" not in roles:
            roles.insert(0, "researcher")
        if "critic" not in roles:
            roles.append("critic")
        return {
            "requested_roles": roles,
            "status": "roles_selected",
            "events": [f"coordinator 选择角色：{', '.join(roles)}"],
        }

    def dispatch_workers(self, state: LLMState) -> list[Any]:
        return [
            Send(
                "specialist_worker",
                {
                    "task": state["task"],
                    "role": role,
                },
            )
            for role in state.get("requested_roles", [])
        ]

    def specialist_worker(self, state: LLMState) -> dict[str, Any]:
        role = str(state.get("role", ""))
        if role not in ROLE_INSTRUCTIONS:
            return {
                "failures": [{"role": role, "error": "未知专家角色"}],
                "events": [f"{role} 失败，已记录 warning"],
            }

        try:
            output = self.call_model(
                ROLE_INSTRUCTIONS[role],
                (
                    f"总任务：{state['task']}\n"
                    "请只处理你负责的角色，不要代替其他专家做最终汇总。"
                ),
            )
            return {
                "worker_results": [
                    {
                        "role": role,
                        "ok": True,
                        "output": output,
                    }
                ],
                "events": [f"{role} Agent 完成"],
            }
        except Exception as error:
            return {
                "failures": [{"role": role, "error": str(error)}],
                "events": [f"{role} Agent 失败，已记录 warning"],
            }

    def synthesizer(self, state: LLMState) -> dict[str, Any]:
        results = json.dumps(
            state.get("worker_results", []),
            ensure_ascii=False,
            indent=2,
        )
        failures = json.dumps(
            state.get("failures", []),
            ensure_ascii=False,
            indent=2,
        )
        try:
            answer = self.call_model(
                (
                    "你是资深汇总 Agent。综合多个专家的结果回答用户任务。"
                    "区分事实、推断和不确定性；不要隐藏专家失败；"
                    "如果证据不足，明确说明不能确认。"
                ),
                (
                    f"任务：{state['task']}\n"
                    f"专家结果：\n{results}\n"
                    f"专家失败：\n{failures}\n"
                    "请输出一份清晰、谨慎、可执行的最终答案。"
                ),
            )
            status = "completed_with_warnings" if state.get("failures") else "completed"
            return {
                "final_answer": answer,
                "status": status,
                "events": ["synthesizer Agent 完成汇总"],
            }
        except Exception as error:
            return {
                "final_answer": "汇总 Agent 执行失败，不能生成可靠最终答案。",
                "status": "failed",
                "failures": [{"role": "synthesizer", "error": str(error)}],
                "events": ["synthesizer Agent 失败"],
            }

    def build_graph(self, checkpointer: Any = None) -> Any:
        require_langgraph()
        builder = StateGraph(LLMState)
        builder.add_node("coordinator", self.coordinator)
        builder.add_node("specialist_worker", self.specialist_worker)
        builder.add_node("synthesizer", self.synthesizer)
        builder.add_edge(START, "coordinator")
        builder.add_conditional_edges(
            "coordinator",
            self.dispatch_workers,
            ["specialist_worker"],
        )
        builder.add_edge("specialist_worker", "synthesizer")
        builder.add_edge("synthesizer", END)
        return builder.compile(checkpointer=checkpointer or InMemorySaver())


def build_llm_graph(client: Any, model: str, checkpointer: Any = None) -> Any:
    return LLMCollaborationRuntime(client, model).build_graph(checkpointer)


def create_client_from_env() -> tuple[Any, str]:
    from dotenv import load_dotenv
    from openai import OpenAI
    import os

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    if not api_key or api_key.startswith(("replace-", "你的")):
        raise ValueError("OPENAI_API_KEY 未配置或仍是占位符")
    if not model:
        raise ValueError("OPENAI_MODEL 未配置")
    if base_url is not None and not base_url.startswith(("http://", "https://")):
        raise ValueError("OPENAI_BASE_URL 必须是 http:// 或 https:// 地址")
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,
        max_retries=2,
    ), model


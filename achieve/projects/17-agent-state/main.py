import argparse
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError


load_dotenv()

STATE_FILE = Path(__file__).with_name("session-state.json")
VALID_STATUSES = {
    "planning",
    "executing",
    "reviewing",
    "completed",
    "failed",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_retryable_error(error: Exception) -> bool:
    if isinstance(error, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    return getattr(error, "status_code", None) in RETRYABLE_STATUS_CODES


def retry_with_backoff(
    operation: Callable[[], Any],
    operation_name: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> Any:
    if max_attempts < 1:
        raise ValueError("max_attempts 必须至少为 1")

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as error:
            if not is_retryable_error(error) or attempt == max_attempts:
                raise

            delay = base_delay * (2 ** (attempt - 1))
            print(
                f"{operation_name}暂时失败，{delay:g} 秒后重试 "
                f"（第 {attempt}/{max_attempts} 次尝试，错误类型：{type(error).__name__}）"
            )
            time.sleep(delay)

    raise RuntimeError("重试流程异常结束")


@dataclass
class AgentState:
    task: str
    status: str = "planning"
    steps: list[str] = field(default_factory=list)
    current_step: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    updated_at: str = field(default_factory=now_iso)

    def validate(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"未知状态：{self.status}")
        if self.current_step < 0 or self.current_step > len(self.steps):
            raise ValueError("current_step 超出步骤范围")


def save_state(state: AgentState) -> None:
    state.updated_at = now_iso()
    state.validate()
    STATE_FILE.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已保存检查点：{STATE_FILE}")


def load_state() -> AgentState:
    if not STATE_FILE.exists():
        raise FileNotFoundError(f"找不到状态文件：{STATE_FILE}")
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state = AgentState(**data)
    state.validate()
    return state


def change_status(state: AgentState, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"未知状态：{status}")
    state.status = status
    save_state(state)


def parse_json_array(content: str) -> list[str]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0]
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ValueError(f"模型没有返回有效 JSON 数组：{content}") from error
    if not isinstance(value, list):
        raise ValueError("模型返回的不是数组")
    items = [str(item).strip() for item in value if str(item).strip()]
    if not 1 <= len(items) <= 5:
        raise ValueError("计划步骤数量必须在 1 到 5 之间")
    return items


def create_plan(client: OpenAI, model: str, task: str) -> list[str]:
    response = retry_with_backoff(
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是任务规划器。把用户任务拆成 1 到 5 个可以顺序执行的步骤。"
                        "每个步骤应该是清晰的行动，不要写解释。"
                        "只返回 JSON 字符串数组。"
                    ),
                },
                {"role": "user", "content": task},
            ],
            temperature=0.2,
        ),
        "生成任务计划",
    )
    content = response.choices[0].message.content or "[]"
    return parse_json_array(content)


def execute_step(
    client: OpenAI,
    model: str,
    state: AgentState,
    step: str,
) -> str:
    previous_results = "\n".join(
        f"步骤 {item['step']}: {item['result']}"
        for item in state.results
    ) or "暂无已完成步骤。"
    response = retry_with_backoff(
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个执行工作流步骤的 Agent。"
                        "只处理当前步骤，不要假装完成其他步骤。"
                        "输出简洁的步骤结果。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"总任务：{state.task}\n"
                        f"当前步骤：{step}\n"
                        f"之前结果：\n{previous_results}"
                    ),
                },
            ],
            temperature=0.2,
        ),
        "执行工作流步骤",
    )
    return response.choices[0].message.content or "当前步骤没有返回结果。"


def review_results(
    client: OpenAI,
    model: str,
    state: AgentState,
) -> str:
    results = "\n".join(
        f"步骤 {item['step']}: {item['result']}"
        for item in state.results
    )
    response = retry_with_backoff(
        lambda: client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是任务审查器。根据已完成步骤整理最终答案。"
                        "如果结果中存在明显缺失，请明确指出，不要编造。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"总任务：{state.task}\n执行结果：\n{results}",
                },
            ],
            temperature=0.2,
        ),
        "审查工作流结果",
    )
    return response.choices[0].message.content or "审查没有返回结果。"


def run_workflow(
    client: OpenAI,
    model: str,
    state: AgentState,
) -> AgentState:
    if not state.steps:
        change_status(state, "planning")
        state.steps = create_plan(client, model, state.task)
        print("生成计划：")
        for index, step in enumerate(state.steps, start=1):
            print(f"  {index}. {step}")
        save_state(state)

    change_status(state, "executing")
    while state.current_step < len(state.steps):
        step_number = state.current_step + 1
        step = state.steps[state.current_step]
        print(f"\n执行步骤 {step_number}/{len(state.steps)}：{step}")
        result = execute_step(client, model, state, step)
        state.results.append(
            {
                "step": step_number,
                "description": step,
                "result": result,
                "completed_at": now_iso(),
            }
        )
        state.current_step += 1
        save_state(state)

    change_status(state, "reviewing")
    state.final_answer = review_results(client, model, state)
    change_status(state, "completed")
    return state


def run_demo() -> None:
    state = AgentState(
        task="演示一个可恢复的学习任务",
        steps=["读取任务状态", "执行当前步骤", "保存检查点", "整理结果"],
    )
    save_state(state)
    change_status(state, "executing")
    for index, step in enumerate(state.steps, start=1):
        # if index == 3:
        #     raise ValueError("主动抛出错误")
        state.results.append(
            {
                "step": index,
                "description": step,
                "result": f"已完成：{step}",
                "completed_at": now_iso(),
            }
        )
        state.current_step = index
        save_state(state)
    change_status(state, "reviewing")
    state.final_answer = "演示任务已完成，所有步骤都保存了检查点。"
    change_status(state, "completed")
    print(f"\n最终状态：{state.status}")
    print(f"最终结果：{state.final_answer}")


def get_client() -> tuple[OpenAI, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")
    return OpenAI(api_key=api_key, base_url=base_url), model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--task")
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    client, model = get_client()
    if args.resume:
        state = load_state()
        print(
            f"恢复任务：{state.task}\n"
            f"状态：{state.status}\n"
            f"进度：{state.current_step}/{len(state.steps)}"
        )
    else:
        task = args.task or input("请输入任务：").strip()
        if not task:
            raise ValueError("任务不能为空")
        state = AgentState(task=task)
        save_state(state)

    try:
        state = run_workflow(client, model, state)
        print(f"\n最终答案：\n{state.final_answer}")
    except Exception as error:
        state.status = "failed"
        save_state(state)
        raise RuntimeError(
            f"工作流执行失败：{error}\n"
            "可以修复问题后使用 --resume 继续。"
        ) from error


if __name__ == "__main__":
    main()

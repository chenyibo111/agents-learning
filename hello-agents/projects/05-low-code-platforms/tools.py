"""带权限和幂等检查的本地工具节点。"""

from dataclasses import dataclass
from typing import Any, Callable


class ToolPermissionError(PermissionError):
    """当前工作流状态没有执行工具所需的权限。"""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    required_permission: str
    handler: Callable[[Any, Any, str], str]


class ToolRegistry:
    def __init__(self, store: Any):
        self.store = store
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def execute(self, name: str, state: Any, *, idempotency_key: str) -> str:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"未知工具：{name}")
        if spec.required_permission not in state.permissions:
            raise ToolPermissionError(f"工具 {name} 缺少权限：{spec.required_permission}")
        return spec.handler(state, self.store, idempotency_key)


def send_email_tool(state: Any, store: Any, idempotency_key: str) -> str:
    """把邮件写入本地 outbox，模拟真实副作用但不访问网络。"""
    record = store.save_outbox(
        idempotency_key=idempotency_key,
        recipient="customer@example.invalid",
        body=state.normalized,
    )
    return f"outbox:{record['id']}"

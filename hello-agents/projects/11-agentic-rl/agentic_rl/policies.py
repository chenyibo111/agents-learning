"""可复现策略。生产系统中此层可替换为模型策略或远程推理服务。"""

from typing import Protocol

from .schemas import Action, TaskCase


class Policy(Protocol):
    name: str

    def propose(self, task: TaskCase) -> list[Action]: ...


class ToolFirstPolicy:
    name = "tool_first"

    def propose(self, task: TaskCase) -> list[Action]:
        return [
            Action("tool:add_numbers", {"a": task.a, "b": task.b}),
            Action("answer", {"value": task.target}),
        ]


class ShortcutPolicy:
    name = "shortcut"

    def propose(self, task: TaskCase) -> list[Action]:
        return [Action("answer", {"value": task.target})]


class WrongPolicy:
    name = "wrong"

    def propose(self, task: TaskCase) -> list[Action]:
        return [Action("answer", {"value": 0})]


class VerbosePolicy:
    name = "verbose"

    def propose(self, task: TaskCase) -> list[Action]:
        return [
            Action("tool:add_numbers", {"a": task.a, "b": task.b}),
            Action("tool:add_numbers", {"a": task.a, "b": task.b}),
            Action("answer", {"value": task.target}),
        ]


class IllegalToolPolicy:
    name = "illegal_tool"

    def propose(self, task: TaskCase) -> list[Action]:
        return [
            Action("tool:delete_files", {}),
            Action("answer", {"value": task.target}),
        ]


_POLICIES: dict[str, Policy] = {
    policy.name: policy
    for policy in (
        ToolFirstPolicy(),
        ShortcutPolicy(),
        WrongPolicy(),
        VerbosePolicy(),
        IllegalToolPolicy(),
    )
}


def get_policy(name: str) -> Policy:
    try:
        return _POLICIES[name]
    except KeyError as exc:
        raise ValueError(f"未知策略: {name}") from exc


def policy_names() -> tuple[str, ...]:
    return tuple(_POLICIES)

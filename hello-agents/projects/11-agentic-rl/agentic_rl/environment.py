"""确定性算术环境：把策略动作映射为可审计的观察结果。"""

from .schemas import Action, Observation, TaskCase


class ArithmeticEnvironment:
    """极小但有明确工具边界的 Agent 环境。"""

    def execute(self, task: TaskCase, action: Action) -> Observation:
        if action.name == "tool:add_numbers":
            expected = {"a": task.a, "b": task.b}
            if action.arguments != expected:
                return Observation("拒绝：参数不匹配", False, "invalid_arguments")
            return Observation(str(task.target), True)
        if action.name == "answer":
            value = action.arguments.get("value")
            return Observation(str(value), True)
        return Observation(f"拒绝：未知动作 {action.name}", False, "unknown_action")

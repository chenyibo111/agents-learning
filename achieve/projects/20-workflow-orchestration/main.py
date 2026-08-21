import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


STATE_FILE = Path(__file__).with_name("workflow-state.json")
VALID_STATUSES = {
    "pending",
    "running",
    "waiting_approval",
    "completed",
    "rejected",
    "failed",
}
VALID_NODES = {
    "prepare",
    "parallel_collect",
    "merge",
    "approval",
    "publish",
    "done",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkflowState:
    task: str
    status: str = "pending"
    current_node: str = "prepare"
    data: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    approval_reason: str = ""
    updated_at: str = field(default_factory=now_iso)

    def validate(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"未知工作流状态：{self.status}")
        if self.current_node not in VALID_NODES:
            raise ValueError(f"未知工作流节点：{self.current_node}")


class WorkflowRunner:
    def __init__(self, state_file: Optional[Path] = None) -> None:
        self.state_file = state_file or STATE_FILE

    def save_state(self, state: WorkflowState) -> None:
        state.updated_at = now_iso()
        state.validate()
        self.state_file.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_state(self) -> WorkflowState:
        if not self.state_file.exists():
            raise FileNotFoundError(f"找不到工作流状态文件：{self.state_file}")
        state = WorkflowState(**json.loads(self.state_file.read_text(encoding="utf-8")))
        state.validate()
        return state

    def run(
        self,
        state: WorkflowState,
        decision: Optional[str] = None,
    ) -> WorkflowState:
        try:
            if state.status in {"completed", "rejected"}:
                return state

            if state.status == "waiting_approval":
                if decision is None:
                    return state
                self._handle_approval(state, decision)
                if state.status == "rejected":
                    return state

            if state.status == "pending":
                state.status = "running"
                self.save_state(state)

            while state.current_node != "done":
                if state.current_node == "prepare":
                    self._record(
                        state,
                        "prepare",
                        {"prepared": True},
                        next_node="parallel_collect",
                    )
                elif state.current_node == "parallel_collect":
                    self._run_parallel_collect(state)
                elif state.current_node == "merge":
                    self._merge_and_route(state)
                    if state.status == "waiting_approval":
                        return state
                elif state.current_node == "publish":
                    self._record(
                        state,
                        "publish",
                        {"published": True},
                        next_node="done",
                    )
                    state.status = "completed"
                    self.save_state(state)
                else:
                    raise ValueError(f"无法执行工作流节点：{state.current_node}")

            return state
        except Exception as error:
            state.status = "failed"
            state.data["error"] = str(error)
            self.save_state(state)
            raise

    def _record(
        self,
        state: WorkflowState,
        node: str,
        updates: dict[str, Any],
        next_node: str,
    ) -> None:
        state.data.update(updates)
        state.history.append(
            {
                "node": node,
                "updates": updates,
                "completed_at": now_iso(),
            }
        )
        state.current_node = next_node
        self.save_state(state)

    def _run_parallel_collect(self, state: WorkflowState) -> None:
        branches = {
            "collect_local": self._collect_local,
            "collect_catalog": self._collect_catalog,
        }
        with ThreadPoolExecutor(max_workers=len(branches)) as executor:
            futures = {
                name: executor.submit(handler, dict(state.data))
                for name, handler in branches.items()
            }
            results = {name: futures[name].result() for name in branches}

        for name, updates in results.items():
            self._record(
                state,
                name,
                updates,
                next_node="parallel_collect" if name == "collect_local" else "merge",
            )

    def _merge_and_route(self, state: WorkflowState) -> None:
        risk_level = state.data.get("risk_level", "low")
        updates = {
            "merged": True,
            "risk_level": risk_level,
            "merged_item_count": len(state.data.get("local_notes", []))
            + len(state.data.get("catalog_items", [])),
        }
        state.data.update(updates)
        state.history.append(
            {
                "node": "merge",
                "updates": updates,
                "completed_at": now_iso(),
            }
        )

        if risk_level == "high":
            state.approval_reason = "任务风险等级为 high，需要人工确认后才能发布。"
            state.current_node = "approval"
            state.status = "waiting_approval"
            state.history.append(
                {
                    "node": "approval_requested",
                    "reason": state.approval_reason,
                    "completed_at": now_iso(),
                }
            )
        else:
            state.current_node = "publish"
        self.save_state(state)

    def _handle_approval(self, state: WorkflowState, decision: str) -> None:
        if decision not in {"approve", "reject"}:
            raise ValueError("审批决定必须是 approve 或 reject")

        if decision == "reject":
            state.status = "rejected"
            state.current_node = "done"
            state.history.append(
                {"node": "approval_rejected", "completed_at": now_iso()}
            )
            self.save_state(state)
            return

        state.status = "running"
        state.current_node = "publish"
        state.history.append(
            {"node": "approval_approved", "completed_at": now_iso()}
        )
        self.save_state(state)

    @staticmethod
    def _collect_local(_: dict[str, Any]) -> dict[str, Any]:
        return {"local_notes": ["Agent 基础循环", "工具调用"]}

    @staticmethod
    def _collect_catalog(_: dict[str, Any]) -> dict[str, Any]:
        return {"catalog_items": ["工作流", "状态机"]}


def print_state(state: WorkflowState) -> None:
    print(f"状态：{state.status}")
    print(f"当前节点：{state.current_node}")
    if state.approval_reason:
        print(f"审批原因：{state.approval_reason}")
    print("数据：")
    print(json.dumps(state.data, ensure_ascii=False, indent=2))
    print("执行历史：")
    for item in state.history:
        print(f"- {item['node']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--high-risk", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reject", action="store_true")
    parser.add_argument("--task")
    args = parser.parse_args()

    if args.approve and args.reject:
        parser.error("--approve 和 --reject 不能同时使用")

    runner = WorkflowRunner()
    decision = "approve" if args.approve else "reject" if args.reject else None
    if args.resume or decision:
        state = runner.load_state()
    else:
        task = args.task or "演示一个可编排的研究任务"
        risk_level = "high" if args.high_risk else "low"
        state = WorkflowState(task=task, data={"risk_level": risk_level})

    result = runner.run(state, decision=decision)
    print_state(result)


if __name__ == "__main__":
    main()

"""版本化 checkpoint、事件轨迹和评测报告。"""

import json
import os
from pathlib import Path
import tempfile
from typing import Any
from datetime import datetime
from uuid import uuid4

from .schemas import GameState


def _atomic_write(path: Path, text: str) -> None:
    """先写同目录临时文件再 replace，避免中断留下截断 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        # fsync 确保内容已交给操作系统；replace 在同一文件系统内是原子替换。
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class CheckpointStore:
    """负责单个 checkpoint 文件的读写和 schema 恢复。"""

    def __init__(self, path: Path):
        """将传入路径标准化为 Path，供 save/load 共用。"""
        self.path = Path(path)

    def save(self, state: GameState) -> None:
        """把完整 GameState 原子写入 JSON；文件包含私有身份，必须受保护。"""
        _atomic_write(self.path, json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def load(self) -> GameState:
        """读取 JSON 并交给 GameState 执行版本检查和对象重建。"""
        return GameState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))


class ArtifactStore:
    """管理一局游戏对外保留的 checkpoint、事件轨迹和评测报告。"""

    def __init__(self, root: Path):
        """绑定一局游戏的工件目录；目录实际在写入时再创建。"""
        self.root = Path(root)

    @staticmethod
    def default_run_directory(
        project_root: Path,
        seed: int,
        now: datetime | None = None,
        run_id: str | None = None,
    ) -> Path:
        """为新对局创建位于项目 `runs/` 目录下且不会覆盖旧记录的路径。"""
        timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")
        unique_id = run_id or uuid4().hex[:8]
        return Path(project_root) / "runs" / f"{timestamp}-seed-{seed}-{unique_id}"

    def write(self, state: GameState, report: dict[str, Any]) -> dict[str, str]:
        """输出一局游戏的三个工件，并返回绝对路径以供 CLI 报告。"""
        self.root.mkdir(parents=True, exist_ok=True)
        # checkpoint 用于恢复；JSONL 用于按事件流式分析；report 是面向人的汇总。
        checkpoint = self.root / "checkpoint.json"
        CheckpointStore(checkpoint).save(state)
        events = self.root / "events.jsonl"
        _atomic_write(events, "".join(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for event in state.events))
        report_path = self.root / "report.json"
        _atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return {"checkpoint": str(checkpoint), "events": str(events), "report": str(report_path)}

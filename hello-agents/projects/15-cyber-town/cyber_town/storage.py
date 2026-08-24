"""checkpoint、事件日志和评测报告的文件存储。"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .schemas import SimulationState


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class CheckpointStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, state: SimulationState) -> None:
        _atomic_write(self.path, json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    def load(self) -> SimulationState:
        return SimulationState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def write(self, state: SimulationState, report: dict[str, Any]) -> dict[str, str]:
        self.root.mkdir(parents=True, exist_ok=True)
        checkpoint = self.root / "checkpoint.json"
        CheckpointStore(checkpoint).save(state)
        events = self.root / "events.jsonl"
        _atomic_write(events, "".join(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for event in state.events))
        report_path = self.root / "report.json"
        _atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return {
            "checkpoint": str(checkpoint),
            "events": str(events),
            "report": str(report_path),
        }

"""检查点和报告的原子 JSON 存储。"""

import json
import os
from pathlib import Path
import tempfile

from .schemas import ResearchState


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


class CheckpointStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def save(self, state: ResearchState) -> None:
        _atomic_write(self.path, json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n")

    def load(self) -> ResearchState:
        return ResearchState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save_run(self, state: ResearchState, report: dict) -> dict[str, str]:
        run_dir = self.root / state.query.query_id
        checkpoint_path = run_dir / "checkpoint.json"
        report_path = run_dir / "report.json"
        CheckpointStore(checkpoint_path).save(state)
        _atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return {
            "run_dir": str(run_dir),
            "checkpoint": str(checkpoint_path),
            "report": str(report_path),
        }

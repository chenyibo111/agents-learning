"""实验产物的原子 JSON/JSONL 存储。"""

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .schemas import AgentRun


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


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save_run(
        self,
        manifest: dict[str, Any],
        runs: list[AgentRun],
        report: dict[str, Any],
    ) -> dict[str, str]:
        run_id = str(manifest["run_id"])
        run_dir = self.root / run_id
        manifest_path = run_dir / "manifest.json"
        trajectories_path = run_dir / "trajectories.jsonl"
        report_path = run_dir / "report.json"
        _atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        trajectories = "".join(json.dumps(run.to_dict(), ensure_ascii=False) + "\n" for run in runs)
        _atomic_write(trajectories_path, trajectories)
        _atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "manifest": str(manifest_path),
            "trajectories": str(trajectories_path),
            "report": str(report_path),
        }

    def load_run(self, run_id: str) -> dict[str, Any]:
        run_dir = self.root / run_id
        with (run_dir / "manifest.json").open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        runs: list[AgentRun] = []
        with (run_dir / "trajectories.jsonl").open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    runs.append(AgentRun.from_dict(json.loads(line)))
        with (run_dir / "report.json").open("r", encoding="utf-8") as handle:
            report = json.load(handle)
        return {"manifest": manifest, "runs": runs, "report": report}

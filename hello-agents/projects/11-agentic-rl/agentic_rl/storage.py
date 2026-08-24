"""可恢复的实验产物存储：JSONL 轨迹 + 原子写入的 manifest/report。"""

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from .schemas import ExperimentManifest, Trajectory


SENSITIVE_FIELD_PARTS = ("api_key", "token", "password", "secret", "authorization")


def _assert_safe(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_FIELD_PARTS):
                raise ValueError(f"产物包含敏感字段: {path}.{key}")
            _assert_safe(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_safe(item, f"{path}[{index}]")


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
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


class TrajectoryStore:
    @staticmethod
    def save(path: str | Path, trajectories: Iterable[Trajectory]) -> None:
        rows = [trajectory.to_dict() for trajectory in trajectories]
        _assert_safe(rows)
        content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        _atomic_write_text(Path(path), content)

    @staticmethod
    def load(path: str | Path) -> list[Trajectory]:
        loaded: list[Trajectory] = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    loaded.append(Trajectory.from_dict(json.loads(line)))
                except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    raise ValueError(f"轨迹文件第 {line_number} 行无效") from exc
        return loaded


class ArtifactStore:
    """一个 run 目录内的三个标准产物，便于 CI、审计和回放。"""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save_run(
        self,
        manifest: ExperimentManifest,
        trajectories: Iterable[Trajectory],
        report: dict[str, Any],
    ) -> dict[str, str]:
        trajectory_items = list(trajectories)
        manifest_data = manifest.to_dict()
        report_data = dict(report)
        _assert_safe(manifest_data)
        _assert_safe(report_data)
        run_dir = self.root / manifest.run_id
        manifest_path = run_dir / "manifest.json"
        trajectory_path = run_dir / "trajectories.jsonl"
        report_path = run_dir / "report.json"
        _atomic_write_text(manifest_path, json.dumps(manifest_data, ensure_ascii=False, indent=2) + "\n")
        TrajectoryStore.save(trajectory_path, trajectory_items)
        _atomic_write_text(report_path, json.dumps(report_data, ensure_ascii=False, indent=2) + "\n")
        return {
            "run_dir": str(run_dir),
            "manifest": str(manifest_path),
            "trajectories": str(trajectory_path),
            "report": str(report_path),
        }

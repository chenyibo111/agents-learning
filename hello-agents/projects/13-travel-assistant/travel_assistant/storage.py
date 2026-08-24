"""预订状态与实验报告的 JSON 持久化。"""

import json
import os
from pathlib import Path
import tempfile

from .schemas import Reservation, ReservationStatus


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


class BookingLedger:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._items: dict[str, Reservation] = {}
        if self.path and self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            for item in payload:
                self._items[item["idempotency_key"]] = Reservation(
                    reservation_id=item["reservation_id"],
                    itinerary_id=item["itinerary_id"],
                    idempotency_key=item["idempotency_key"],
                    status=ReservationStatus(item["status"]),
                    created_at=__import__("datetime").datetime.fromisoformat(item["created_at"]),
                    approved_by=item.get("approved_by"),
                    reason=item.get("reason"),
                )

    def get(self, idempotency_key: str) -> Reservation | None:
        return self._items.get(idempotency_key)

    def put(self, reservation: Reservation) -> None:
        self._items[reservation.idempotency_key] = reservation
        if self.path:
            content = json.dumps(
                [item.to_dict() for item in self._items.values()],
                ensure_ascii=False,
                indent=2,
            )
            _atomic_write(self.path, content + "\n")


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def save_report(self, report: dict) -> dict[str, str]:
        run_dir = self.root / str(report["request"]["request_id"])
        report_path = run_dir / "report.json"
        _atomic_write(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return {"run_dir": str(run_dir), "report": str(report_path)}

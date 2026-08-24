"""需要审批的幂等预订状态机。"""

from datetime import datetime
import hashlib

from .schemas import Itinerary, Reservation, ReservationStatus
from .storage import BookingLedger


class BookingService:
    def __init__(self, ledger: BookingLedger | None = None):
        self.ledger = ledger or BookingLedger()

    def request_reservation(self, itinerary: Itinerary | dict, idempotency_key: str) -> Reservation:
        if not idempotency_key.strip():
            raise ValueError("预订必须提供幂等键")
        existing = self.ledger.get(idempotency_key)
        if existing:
            return existing
        itinerary_id = itinerary.itinerary_id if isinstance(itinerary, Itinerary) else str(itinerary["itinerary_id"])
        reservation_id = "res-" + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:12]
        reservation = Reservation(
            reservation_id=reservation_id,
            itinerary_id=itinerary_id,
            idempotency_key=idempotency_key,
            status=ReservationStatus.PENDING_APPROVAL,
            created_at=datetime.now().astimezone(),
            reason="approval_required",
        )
        self.ledger.put(reservation)
        return reservation

    def approve(self, idempotency_key: str, approver: str) -> Reservation:
        if not approver.strip():
            raise ValueError("审批必须记录审批人")
        reservation = self.ledger.get(idempotency_key)
        if reservation is None:
            raise ValueError("找不到待审批预订")
        if reservation.status == ReservationStatus.CONFIRMED:
            return reservation
        confirmed = Reservation(
            reservation_id=reservation.reservation_id,
            itinerary_id=reservation.itinerary_id,
            idempotency_key=reservation.idempotency_key,
            status=ReservationStatus.CONFIRMED,
            created_at=reservation.created_at,
            approved_by=approver,
            reason="approved",
        )
        self.ledger.put(confirmed)
        return confirmed

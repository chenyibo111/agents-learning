"""第 13 课离线旅行实验编排。"""

from .booking import BookingService
from .normalization import normalize_request
from .planner import plan_trip, public_plan
from .providers import FixtureProviders
from .storage import ArtifactStore


def run_demo(
    *,
    weather_failure: bool = False,
    inventory_expired: bool = False,
    approve: bool = False,
    output_dir: str | None = None,
) -> dict:
    request = normalize_request(
        {
            "request_id": "demo-trip-001",
            "origin": "北京",
            "destination": "上海",
            "departure_date": "2026-09-01",
            "return_date": "2026-09-03",
            "travelers": 1,
            "budget": 2000,
            "currency": "CNY",
            "timezone": "Asia/Shanghai",
            "avoid_rain": False,
            "passport_number": "P123456",
            "contact_phone": "13800000000",
        }
    )
    providers = FixtureProviders(
        weather_failure=weather_failure,
        inventory_expired=inventory_expired,
    )
    plan = plan_trip(request, providers)
    service = BookingService()
    reservation = None
    if plan.candidates:
        reservation = service.request_reservation(plan.candidates[0], "demo-idempotency-key")
        if approve:
            reservation = service.approve("demo-idempotency-key", "demo-approver")
    report = {
        "request": request.to_dict(public=True),
        "plan": public_plan(plan, request),
        "reservation": reservation.to_dict() if reservation else None,
        "side_effects": {"external_booking_executed": bool(reservation and approve)},
    }
    if output_dir:
        report["artifacts"] = ArtifactStore(output_dir).save_report(report)
    return report

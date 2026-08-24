import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "13-travel-assistant"
sys.path.insert(0, str(PROJECT))

from travel_assistant.booking import BookingService
from travel_assistant.experiment import run_demo
from travel_assistant.normalization import normalize_request, to_cny
from travel_assistant.planner import plan_trip, public_plan
from travel_assistant.providers import FixtureProviders
from travel_assistant.schemas import ReservationStatus
from travel_assistant.storage import BookingLedger


def request_payload(**overrides):
    payload = {
        "request_id": "trip-001",
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
    payload.update(overrides)
    return payload


class TravelAssistantTests(unittest.TestCase):
    def test_request_normalization_validates_dates_and_currency(self):
        request = normalize_request(request_payload(currency="USD", budget=300))
        self.assertEqual("USD", request.currency)
        self.assertEqual("2026-09-01", request.departure_date.isoformat())
        self.assertEqual(2160.0, to_cny(request.budget, request.currency))
        with self.assertRaises(ValueError):
            normalize_request(request_payload(return_date="2026-08-01"))

    def test_fixture_provider_returns_timezone_aware_expiring_inventory(self):
        request = normalize_request(request_payload())
        providers = FixtureProviders()
        flights = providers.flights.search(request)
        self.assertTrue(flights)
        self.assertIsNotNone(flights[0].expires_at.tzinfo)
        self.assertEqual("fixture-flight", flights[0].source)

    def test_planner_filters_to_budget_and_returns_candidates(self):
        request = normalize_request(request_payload(budget=2000))
        plan = plan_trip(request, FixtureProviders())
        self.assertTrue(plan.candidates)
        self.assertTrue(all(item.total_cost_cny <= 2000 for item in plan.candidates))
        self.assertTrue(all(item.requires_approval for item in plan.candidates))

    def test_expired_inventory_is_rejected(self):
        request = normalize_request(request_payload())
        plan = plan_trip(request, FixtureProviders(inventory_expired=True))
        self.assertFalse(plan.candidates)
        self.assertIn("inventory_expired", plan.rejected_reasons)

    def test_weather_failure_degrades_with_warning(self):
        request = normalize_request(request_payload())
        plan = plan_trip(request, FixtureProviders(weather_failure=True))
        self.assertTrue(plan.candidates)
        self.assertIn("weather_unavailable", plan.warnings)

    def test_public_plan_redacts_sensitive_request_fields(self):
        request = normalize_request(request_payload())
        plan = plan_trip(request, FixtureProviders())
        report = public_plan(plan, request)
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("P123456", serialized)
        self.assertNotIn("13800000000", serialized)
        self.assertEqual("[REDACTED]", report["request"]["passport_number"])

    def test_booking_requires_approval(self):
        result = run_demo()
        itinerary = result["plan"]["candidates"][0]
        service = BookingService()
        reservation = service.request_reservation(itinerary, "idem-001")
        self.assertEqual(ReservationStatus.PENDING_APPROVAL, reservation.status)
        self.assertEqual("approval_required", reservation.reason)

    def test_approval_confirms_reservation(self):
        result = run_demo()
        itinerary = result["plan"]["candidates"][0]
        service = BookingService()
        service.request_reservation(itinerary, "idem-002")
        confirmed = service.approve("idem-002", "alice")
        self.assertEqual(ReservationStatus.CONFIRMED, confirmed.status)
        self.assertEqual("alice", confirmed.approved_by)

    def test_idempotency_returns_same_reservation_after_restart(self):
        result = run_demo()
        itinerary = result["plan"]["candidates"][0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bookings.json"
            first_service = BookingService(BookingLedger(path))
            first = first_service.request_reservation(itinerary, "idem-003")
            second_service = BookingService(BookingLedger(path))
            second = second_service.request_reservation(itinerary, "idem-003")
        self.assertEqual(first.reservation_id, second.reservation_id)

    def test_cli_demo_writes_json_artifacts_and_supports_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--json",
                    "--approve",
                    "--output-dir",
                    directory,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertEqual("CONFIRMED", payload["reservation"]["status"])
            self.assertTrue(Path(payload["artifacts"]["report"]).exists())


if __name__ == "__main__":
    unittest.main()

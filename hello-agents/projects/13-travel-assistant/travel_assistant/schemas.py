"""旅行需求、资源、行程和预订状态的数据契约。"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class ReservationStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TravelRequest:
    request_id: str
    origin: str
    destination: str
    departure_date: date
    return_date: date
    travelers: int
    budget: float
    currency: str
    timezone: str
    avoid_rain: bool = False
    passport_number: str | None = None
    contact_phone: str | None = None

    def to_dict(self, *, public: bool = False) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date.isoformat(),
            "return_date": self.return_date.isoformat(),
            "travelers": self.travelers,
            "budget": self.budget,
            "currency": self.currency,
            "timezone": self.timezone,
            "avoid_rain": self.avoid_rain,
            "passport_number": "[REDACTED]" if public and self.passport_number else self.passport_number,
            "contact_phone": "[REDACTED]" if public and self.contact_phone else self.contact_phone,
        }


@dataclass(frozen=True)
class FlightOption:
    flight_id: str
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    price: float
    currency: str
    available_seats: int
    source: str
    fetched_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class HotelOption:
    hotel_id: str
    city: str
    check_in: date
    check_out: date
    total_price: float
    currency: str
    available_rooms: int
    source: str
    fetched_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class WeatherReport:
    city: str
    forecast_date: date
    condition: str
    temperature_c: float
    source: str
    fetched_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


@dataclass(frozen=True)
class Itinerary:
    itinerary_id: str
    request_id: str
    flight_id: str
    hotel_id: str
    total_cost: float
    currency: str
    total_cost_cny: float
    weather_condition: str | None
    warnings: tuple[str, ...] = ()
    requires_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "itinerary_id": self.itinerary_id,
            "request_id": self.request_id,
            "flight_id": self.flight_id,
            "hotel_id": self.hotel_id,
            "total_cost": self.total_cost,
            "currency": self.currency,
            "total_cost_cny": self.total_cost_cny,
            "weather_condition": self.weather_condition,
            "warnings": list(self.warnings),
            "requires_approval": self.requires_approval,
        }


@dataclass(frozen=True)
class TravelPlan:
    request_id: str
    generated_at: datetime
    candidates: tuple[Itinerary, ...]
    warnings: tuple[str, ...] = ()
    rejected_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    itinerary_id: str
    idempotency_key: str
    status: ReservationStatus
    created_at: datetime
    approved_by: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "itinerary_id": self.itinerary_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_by": self.approved_by,
            "reason": self.reason,
        }

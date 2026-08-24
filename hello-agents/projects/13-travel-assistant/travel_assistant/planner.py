"""纯规划层：只查询资源和生成候选，不执行预订副作用。"""

from datetime import datetime

from .normalization import from_cny, to_cny
from .providers import FixtureProviders, ProviderError
from .schemas import Itinerary, TravelPlan, TravelRequest


def plan_trip(
    request: TravelRequest,
    providers: FixtureProviders,
    *,
    now: datetime | None = None,
) -> TravelPlan:
    current = now or providers.now
    warnings: list[str] = []
    rejected: list[str] = []
    flights = providers.flights.search(request)
    hotels = providers.hotels.search(request)
    try:
        weather = providers.weather.forecast(request)
        weather_condition = weather.condition
        if weather.is_expired(current):
            weather_condition = None
            warnings.append("weather_expired")
    except ProviderError as exc:
        weather_condition = None
        warnings.append(str(exc))

    valid_flights = []
    for flight in flights:
        if flight.is_expired(current):
            rejected.append("inventory_expired")
        elif flight.available_seats < request.travelers:
            rejected.append("flight_capacity")
        else:
            valid_flights.append(flight)
    valid_hotels = []
    for hotel in hotels:
        if hotel.is_expired(current):
            rejected.append("inventory_expired")
        elif hotel.available_rooms < request.travelers:
            rejected.append("hotel_capacity")
        else:
            valid_hotels.append(hotel)

    candidates: list[Itinerary] = []
    budget_cny = to_cny(request.budget, request.currency)
    for flight in valid_flights:
        for hotel in valid_hotels:
            total_cny = round(to_cny(flight.price, flight.currency) + to_cny(hotel.total_price, hotel.currency), 2)
            if total_cny > budget_cny:
                rejected.append("budget_exceeded")
                continue
            if request.avoid_rain and weather_condition == "rain":
                rejected.append("weather_constraint")
                continue
            candidates.append(
                Itinerary(
                    itinerary_id=f"{request.request_id}-{flight.flight_id}-{hotel.hotel_id}",
                    request_id=request.request_id,
                    flight_id=flight.flight_id,
                    hotel_id=hotel.hotel_id,
                    total_cost=from_cny(total_cny, request.currency),
                    currency=request.currency,
                    total_cost_cny=total_cny,
                    weather_condition=weather_condition,
                    warnings=tuple(warnings),
                )
            )
    return TravelPlan(
        request_id=request.request_id,
        generated_at=current,
        candidates=tuple(candidates),
        warnings=tuple(sorted(set(warnings))),
        rejected_reasons=tuple(sorted(set(rejected))),
    )


def public_plan(plan: TravelPlan, request: TravelRequest) -> dict:
    return {
        "request": request.to_dict(public=True),
        "generated_at": plan.generated_at.isoformat(),
        "candidates": [candidate.to_dict() for candidate in plan.candidates],
        "warnings": list(plan.warnings),
        "rejected_reasons": list(plan.rejected_reasons),
    }

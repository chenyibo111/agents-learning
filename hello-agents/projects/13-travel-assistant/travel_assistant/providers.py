"""可替换旅行工具协议和离线 Fixture Provider。"""

from datetime import datetime, time, timedelta

from .normalization import resolve_timezone
from .schemas import FlightOption, HotelOption, TravelRequest, WeatherReport


class ProviderError(RuntimeError):
    pass


class FixtureFlightProvider:
    def __init__(self, *, now: datetime, inventory_expired: bool = False):
        self.now = now
        self.inventory_expired = inventory_expired

    def search(self, request: TravelRequest) -> list[FlightOption]:
        expires_at = self.now - timedelta(minutes=1) if self.inventory_expired else self.now + timedelta(hours=4)
        departure_at = datetime.combine(request.departure_date, time(9), tzinfo=self.now.tzinfo)
        arrival_at = departure_at + timedelta(hours=2)
        return [
            FlightOption("flight-001", request.origin, request.destination, departure_at, arrival_at, 900, "CNY", 3, "fixture-flight", self.now, expires_at),
            FlightOption("flight-002", request.origin, request.destination, departure_at.replace(hour=14), arrival_at.replace(hour=16), 1400, "CNY", 3, "fixture-flight", self.now, expires_at),
        ]


class FixtureHotelProvider:
    def __init__(self, *, now: datetime, inventory_expired: bool = False):
        self.now = now
        self.inventory_expired = inventory_expired

    def search(self, request: TravelRequest) -> list[HotelOption]:
        expires_at = self.now - timedelta(minutes=1) if self.inventory_expired else self.now + timedelta(hours=4)
        return [
            HotelOption("hotel-001", request.destination, request.departure_date, request.return_date, 700, "CNY", 3, "fixture-hotel", self.now, expires_at),
            HotelOption("hotel-002", request.destination, request.departure_date, request.return_date, 1300, "CNY", 3, "fixture-hotel", self.now, expires_at),
        ]


class FixtureWeatherProvider:
    def __init__(self, *, now: datetime, failure: bool = False):
        self.now = now
        self.failure = failure

    def forecast(self, request: TravelRequest) -> WeatherReport:
        if self.failure:
            raise ProviderError("weather_unavailable")
        return WeatherReport(
            request.destination,
            request.departure_date,
            "sunny",
            27.0,
            "fixture-weather",
            self.now,
            self.now + timedelta(hours=6),
        )


class FixtureProviders:
    def __init__(self, *, weather_failure: bool = False, inventory_expired: bool = False):
        self.now = datetime(2026, 8, 24, 9, 0, tzinfo=resolve_timezone("Asia/Shanghai"))
        self.flights = FixtureFlightProvider(now=self.now, inventory_expired=inventory_expired)
        self.hotels = FixtureHotelProvider(now=self.now, inventory_expired=inventory_expired)
        self.weather = FixtureWeatherProvider(now=self.now, failure=weather_failure)

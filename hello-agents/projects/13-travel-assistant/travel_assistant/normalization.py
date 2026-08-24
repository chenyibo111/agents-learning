"""旅行需求校验、时区确认、币种换算和隐私脱敏。"""

from datetime import date, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .schemas import TravelRequest


CURRENCY_RATES_TO_CNY = {"CNY": 1.0, "USD": 7.2, "EUR": 7.8}
FALLBACK_TIMEZONES = {"Asia/Shanghai": timezone(timedelta(hours=8), name="CST")}


def resolve_timezone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        try:
            return FALLBACK_TIMEZONES[name]
        except KeyError as exc:
            raise ValueError(f"无法解析时区: {name}") from exc


def to_cny(amount: float, currency: str) -> float:
    try:
        return round(float(amount) * CURRENCY_RATES_TO_CNY[currency.upper()], 2)
    except KeyError as exc:
        raise ValueError(f"不支持的币种: {currency}") from exc


def from_cny(amount_cny: float, currency: str) -> float:
    try:
        return round(float(amount_cny) / CURRENCY_RATES_TO_CNY[currency.upper()], 2)
    except KeyError as exc:
        raise ValueError(f"不支持的币种: {currency}") from exc


def normalize_request(payload: dict) -> TravelRequest:
    required = (
        "request_id", "origin", "destination", "departure_date", "return_date",
        "travelers", "budget", "currency", "timezone",
    )
    missing = [field for field in required if not payload.get(field)]
    if missing:
        raise ValueError(f"缺少旅行需求字段: {', '.join(missing)}")
    try:
        departure = date.fromisoformat(str(payload["departure_date"]))
        return_date = date.fromisoformat(str(payload["return_date"]))
    except ValueError as exc:
        raise ValueError("日期必须使用 YYYY-MM-DD") from exc
    if return_date <= departure:
        raise ValueError("返程日期必须晚于出发日期")
    try:
        travelers = int(payload["travelers"])
        budget = float(payload["budget"])
        currency = str(payload["currency"]).upper()
        resolve_timezone(str(payload["timezone"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("旅行人数、预算或时区无效") from exc
    if travelers <= 0 or budget <= 0:
        raise ValueError("旅行人数和预算必须大于 0")
    to_cny(budget, currency)
    return TravelRequest(
        request_id=str(payload["request_id"]),
        origin=str(payload["origin"]),
        destination=str(payload["destination"]),
        departure_date=departure,
        return_date=return_date,
        travelers=travelers,
        budget=budget,
        currency=currency,
        timezone=str(payload["timezone"]),
        avoid_rain=bool(payload.get("avoid_rain", False)),
        passport_number=payload.get("passport_number"),
        contact_phone=payload.get("contact_phone"),
    )

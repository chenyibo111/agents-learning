# Travel Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade lesson 13 from a budget-only demo into a safe, replayable travel planning and approval workflow.

**Architecture:** Normalize a structured travel request, query replaceable providers, produce a pure itinerary plan, and keep booking behind an approval/idempotency state machine. The default implementation uses deterministic fixture data and JSON artifacts, so no external side effect occurs during offline demos.

**Tech Stack:** Python standard library, `dataclasses`, `datetime`, `zoneinfo`, `unittest`, JSON/JSONL; no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-08-24-travel-assistant-design.md`

## Global Constraints

- Default path is deterministic and offline.
- Planning never confirms a reservation.
- Booking requires explicit approval and a non-empty idempotency key.
- All comparisons normalize money to CNY and all timestamps carry a timezone.
- Sensitive request fields are redacted before persistence or reporting.
- Preserve existing lesson 11 and 12 committed code.

---

### Task 1: Domain schemas, normalization, and provider fixtures

**Files:**
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/schemas.py`
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/normalization.py`
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/providers.py`
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/__init__.py`
- Create: `hello-agents/tests/test_travel_assistant.py`

**Interfaces:**
- Produce `TravelRequest`, `FlightOption`, `HotelOption`, `WeatherReport`, `Itinerary`, `TravelPlan`, `Reservation`, `normalize_request`, `to_cny`, and fixture Provider classes.

- [ ] Write tests for request validation, currency conversion, timezone-aware timestamps, fixture results and expired inventory.
- [ ] Run the focused test file and confirm failure because the package does not exist.
- [ ] Implement the schemas, normalization helpers, privacy redaction and deterministic providers.
- [ ] Re-run focused tests and verify they pass.

### Task 2: Planner, constraints, weather degradation, and privacy-safe reports

**Files:**
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/planner.py`
- Modify: `hello-agents/tests/test_travel_assistant.py`

**Interfaces:**
- Produce `plan_trip(request, providers, now=None) -> TravelPlan` and `public_plan(plan, request) -> dict`.
- Planner filters destination/date/budget/availability/weather constraints and never calls booking code.

- [ ] Add failing tests for budget filtering, expired inventory, weather failure fallback, and redaction of passport/phone.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement pure candidate construction, explicit rejection reasons, warning collection and public report redaction.
- [ ] Re-run focused tests and verify they pass.

### Task 3: Approval, idempotent booking, persistence, and recovery

**Files:**
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/booking.py`
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/storage.py`
- Modify: `hello-agents/tests/test_travel_assistant.py`

**Interfaces:**
- Produce `BookingService.request_reservation(itinerary, idempotency_key)`, `BookingService.approve(idempotency_key, approver)`, and JSON-backed `BookingLedger`.
- States are `PENDING_APPROVAL`, `CONFIRMED`, and `REJECTED`; duplicate idempotency keys return the original reservation.

- [ ] Add failing tests for approval blocking, confirmation, duplicate requests and persistence round-trip.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement the state machine, explicit approver requirement, atomic JSON persistence and restart-safe recovery.
- [ ] Re-run focused tests and verify they pass.

### Task 4: Experiment CLI, documentation, progress, and integration verification

**Files:**
- Create: `hello-agents/projects/13-travel-assistant/travel_assistant/experiment.py`
- Modify: `hello-agents/projects/13-travel-assistant/main.py`
- Modify: `hello-agents/projects/13-travel-assistant/README.md`
- Modify: `hello-agents/tests/test_projects.py`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/CURRICULUM.md`

**Interfaces:**
- Produce `run_demo(weather_failure=False, inventory_expired=False, approve=False)` and CLI flags `--demo`, `--json`, `--weather-failure`, `--inventory-expired`, `--approve`, and `--output-dir`.

- [ ] Add failing integration tests for offline demo, JSON artifacts, weather failure and approval output.
- [ ] Run integration tests and confirm failure before the CLI is refactored.
- [ ] Implement the orchestrator, CLI and artifact report without network access.
- [ ] Document planning/execution boundaries and verification commands.
- [ ] Run lesson tests, all project offline demos, `git diff --check`, and record any unrelated full-suite environment failures.

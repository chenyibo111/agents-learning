"""本地单房间狼人杀 Web 审计服务。"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from .engine import GameEngine
from .policies import LLMPolicy, ModelAdapter
from .rules import finish_draw, initial_game
from .schemas import GameState
from .storage import RequestTraceStore


HTML_PATH = Path(__file__).with_name("web.html")


class RoomConflictError(Exception):
    """服务实例已有一个仍在运行的房间。"""


class RoomNotFoundError(Exception):
    """请求的房间不存在。"""


class InvalidCursorError(ValueError):
    """事件增量游标不是非负整数。"""


class RequestTraceCollector:
    """保存脱敏的逻辑请求摘要，并为 API 提供独立游标。"""

    def __init__(self, path: Path | None = None):
        self._lock = threading.RLock()
        self._records: list[dict[str, Any]] = []
        self._store = RequestTraceStore(path) if path is not None else None

    def append(self, record: dict[str, Any]) -> None:
        safe_record = dict(record)
        with self._lock:
            self._records.append(safe_record)
            if self._store is not None:
                self._store.append(safe_record)

    def snapshot(self, after: int = 0) -> tuple[list[dict[str, Any]], int]:
        if after < 0:
            raise InvalidCursorError("request_after must be a non-negative integer")
        with self._lock:
            return list(self._records[after:]), len(self._records)


def _build_policies(
    state: GameState,
    policy_mode: str,
    model_adapter: ModelAdapter | None,
    on_request,
) -> dict[str, LLMPolicy]:
    """按服务端选定模式创建每名玩家的 Policy。"""
    if policy_mode == "rule":
        return {}
    if policy_mode != "llm":
        raise ValueError("policy_mode must be rule or llm")
    if model_adapter is None:
        raise ValueError("llm policy mode requires a model adapter")
    return {
        player.player_id: LLMPolicy(player.player_id, model_adapter, on_request=on_request)
        for player in state.players
    }


class Room:
    """持有完整 GameState，并在后台按阶段自动推进。"""

    def __init__(
        self,
        state: GameState,
        *,
        step_interval: float = 0.5,
        max_rounds: int = 4,
        policies: Mapping[str, Any] | None = None,
        policy_mode: str = "rule",
        model_name: str = "",
        pricing_configured: bool = False,
        request_collector: RequestTraceCollector | None = None,
    ):
        self.state = state
        self.engine = GameEngine(seed=state.seed, policies=policies)
        self.step_interval = max(0.0, float(step_interval))
        self.max_rounds = max(1, int(max_rounds))
        self.policy_mode = policy_mode
        self.model_name = model_name
        self.pricing_configured = pricing_configured
        self.request_collector = request_collector or RequestTraceCollector()
        self._state_lock = threading.RLock()
        self._step_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.worker_error: str | None = None

    @property
    def game_id(self) -> str:
        return self.state.game_id

    @property
    def running(self) -> bool:
        with self._state_lock:
            return bool(self._thread and self._thread.is_alive() and self.state.status == "RUNNING")

    def step_once(self) -> GameState:
        """推进一个阶段；该方法是 worker 和测试共用的单步边界。"""
        with self._step_lock:
            with self._state_lock:
                current_state = self.state
            if current_state.status != "RUNNING":
                self._done_event.set()
                return current_state
            if current_state.round_number > self.max_rounds:
                next_state = finish_draw(current_state)
            else:
                # 模型请求在状态锁之外执行，审计 API 可以读取最近一次已提交快照。
                next_state = self.engine.step(current_state)
            with self._state_lock:
                self.state = next_state
            if next_state.status != "RUNNING":
                self._done_event.set()
            return next_state

    def start(self) -> None:
        """幂等启动 daemon worker。"""
        with self._state_lock:
            if self.state.status != "RUNNING":
                self._done_event.set()
                return
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name=f"werewolf-room-{self.game_id}", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                if self._stop_event.wait(self.step_interval):
                    return
                self.step_once()
                if not self.running and self.state.status != "RUNNING":
                    return
        except Exception as exc:  # pragma: no cover - exercised through the observable worker error state
            with self._state_lock:
                self.worker_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                self.state = replace(self.state, status="ERROR")
                self._done_event.set()

    def stop(self) -> None:
        with self._state_lock:
            self._stop_event.set()
            thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def wait_until_done(self, timeout: float = 2.0) -> bool:
        """等待终态或 worker 错误，返回是否已停止。"""
        with self._state_lock:
            status = self.state.status
        if status != "RUNNING":
            return True
        return self._done_event.wait(timeout=max(0.0, timeout))

    def snapshot(self, after: int = 0, request_after: int = 0) -> dict[str, Any]:
        """返回完整审计状态和指定游标之后的事件。"""
        if after < 0:
            raise InvalidCursorError("after must be a non-negative integer")
        with self._state_lock:
            current_state = self.state
            running = bool(self._thread and self._thread.is_alive() and current_state.status == "RUNNING")
            worker_error = self.worker_error
        events = current_state.events[after:]
        request_records, request_cursor = self.request_collector.snapshot(request_after)
        return {
            "game_id": current_state.game_id,
            "policy_mode": self.policy_mode,
            "model": self.model_name or None,
            "pricing_configured": self.pricing_configured,
            "state": current_state.to_dict(),
            "events": [event.to_dict() for event in events],
            "cursor": len(current_state.events),
            "llm_requests": request_records,
            "request_cursor": request_cursor,
            "running": running,
            "worker_error": worker_error,
            "artifacts": {},
        }


class RoomStore:
    """服务实例内最多维护一个活动房间。"""

    def __init__(
        self,
        *,
        step_interval: float = 0.5,
        max_rounds: int = 4,
        default_seed: int = 7,
        policy_mode: str = "rule",
        model_adapter: ModelAdapter | None = None,
    ):
        if policy_mode not in {"rule", "llm"}:
            raise ValueError("policy_mode must be rule or llm")
        self.step_interval = step_interval
        self.max_rounds = max_rounds
        self.default_seed = default_seed
        self.policy_mode = policy_mode
        self.model_adapter = model_adapter
        self._lock = threading.RLock()
        self._room: Room | None = None

    def create(self, seed: int | None = None) -> Room:
        with self._lock:
            if self._room is not None and self._room.state.status == "RUNNING":
                raise RoomConflictError("an active room already exists")
            if self._room is not None:
                self._room.stop()
            state = initial_game(self.default_seed if seed is None else seed)
            collector = RequestTraceCollector()
            policies = _build_policies(state, self.policy_mode, self.model_adapter, collector.append)
            model_name = getattr(self.model_adapter, "model", "") if self.policy_mode == "llm" else ""
            pricing_configured = bool(
                self.policy_mode == "llm"
                and self.model_adapter is not None
                and (
                    getattr(self.model_adapter, "input_price_per_million", 0.0) > 0
                    or getattr(self.model_adapter, "output_price_per_million", 0.0) > 0
                )
            )
            self._room = Room(
                state,
                step_interval=self.step_interval,
                max_rounds=self.max_rounds,
                policies=policies,
                policy_mode=self.policy_mode,
                model_name=model_name,
                pricing_configured=pricing_configured,
                request_collector=collector,
            )
            return self._room

    def get(self, game_id: str) -> Room:
        with self._lock:
            if self._room is None or self._room.game_id != game_id:
                raise RoomNotFoundError(game_id)
            return self._room

    def current(self) -> Room | None:
        with self._lock:
            return self._room

    def close(self) -> None:
        with self._lock:
            room = self._room
        if room is not None:
            room.stop()


def _cursor(query: dict[str, list[str]], name: str = "after") -> int:
    value = query.get(name, ["0"])[0]
    try:
        result = int(value)
    except ValueError as exc:
        raise InvalidCursorError(f"{name} must be a non-negative integer") from exc
    if result < 0:
        raise InvalidCursorError(f"{name} must be a non-negative integer")
    return result


def _summary(room: Room) -> dict[str, Any]:
    with room._state_lock:
        state = room.state
        return {
            "game_id": state.game_id,
            "seed": state.seed,
            "policy_mode": room.policy_mode,
            "model": room.model_name or None,
            "pricing_configured": room.pricing_configured,
            "phase": state.phase.value,
            "round_number": state.round_number,
            "status": state.status,
            "winner": state.winner,
            "running": room.running,
        }


def public_snapshot(room: Room, after: int = 0) -> dict[str, Any]:
    """构造不含身份、待行动和私有事件的公开视图。"""
    if after < 0:
        raise InvalidCursorError("after must be a non-negative integer")
    with room._state_lock:
        state = room.state
        public_events = [event for event in state.events[after:] if event.public]
        return {
            "game_id": state.game_id,
            "state": {
                "game_id": state.game_id,
                "seed": state.seed,
                "round_number": state.round_number,
                "phase": state.phase.value,
                "players": [{"player_id": player.player_id, "alive": player.alive} for player in state.players],
                "status": state.status,
                "winner": state.winner,
                "metrics": dict(state.metrics),
            },
            "events": [event.to_dict() for event in public_events],
            "cursor": len(state.events),
            "running": room.running,
        }


def make_handler(store: RoomStore, html_path: Path = HTML_PATH):
    """生成绑定指定 RoomStore 的标准库 HTTP handler。"""

    class Handler(BaseHTTPRequestHandler):
        server_version = "WerewolfArenaWeb/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: int, error: str, message: str) -> None:
            self._send_json({"error": error, "message": message}, status)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("request body must be a JSON object")
            return value

        def _room_route(self, path: list[str]) -> tuple[Room, str] | None:
            if len(path) != 4 or path[:2] != ["api", "rooms"]:
                return None
            return store.get(path[2]), path[3]

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path == "/":
                try:
                    body = html_path.read_bytes()
                except OSError:
                    self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "page_unavailable", "audit page is unavailable")
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            path = [part for part in parsed.path.split("/") if part]
            try:
                if path == ["api", "rooms"]:
                    room = store.current()
                    if room is None:
                        raise RoomNotFoundError("no active room")
                    self._send_json(_summary(room))
                    return
                route = self._room_route(path)
                if route is None or route[1] not in {"audit", "public"}:
                    self._send_error(HTTPStatus.NOT_FOUND, "not_found", "route not found")
                    return
                room, view = route
                query = parse_qs(parsed.query)
                after = _cursor(query, "after")
                request_after = _cursor(query, "request_after")
                self._send_json(
                    room.snapshot(after, request_after) if view == "audit" else public_snapshot(room, after)
                )
            except RoomNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "room_not_found", "room not found")
            except InvalidCursorError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid_cursor", str(exc))
            except Exception:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "request failed")

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            path = [part for part in parsed.path.split("/") if part]
            try:
                if path == ["api", "rooms"]:
                    body = self._body()
                    seed = body.get("seed", store.default_seed)
                    if isinstance(seed, bool) or not isinstance(seed, int):
                        raise ValueError("seed must be an integer")
                    room = store.create(seed=seed)
                    self._send_json(_summary(room), HTTPStatus.CREATED)
                    return
                if len(path) == 4 and path[:2] == ["api", "rooms"] and path[3] == "start":
                    room = store.get(path[2])
                    room.start()
                    self._send_json(_summary(room))
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "not_found", "route not found")
            except RoomConflictError:
                self._send_error(HTTPStatus.CONFLICT, "room_conflict", "an active room already exists")
            except RoomNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "room_not_found", "room not found")
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid_request", str(exc))
            except Exception:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "request failed")

    return Handler


def build_server(host: str = "127.0.0.1", port: int = 8765, *, store: RoomStore | None = None) -> ThreadingHTTPServer:
    room_store = store or RoomStore()
    server = ThreadingHTTPServer((host, port), make_handler(room_store))
    server.room_store = room_store  # type: ignore[attr-defined]
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="启动本地狼人杀上帝视角审计台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--step-interval", type=float, default=0.5)
    args = parser.parse_args()
    store = RoomStore(step_interval=args.step_interval, default_seed=args.seed)
    room = store.create(seed=args.seed)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    print(f"狼人杀上帝视角审计台：{room.game_id} http://{args.host}:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        store.close()


if __name__ == "__main__":
    main()

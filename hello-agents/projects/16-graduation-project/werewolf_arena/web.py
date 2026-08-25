"""本地单房间狼人杀 Web 审计服务。"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import parse_qs, urlparse

from .engine import GameEngine
from .evaluation import evaluate_game
from .policies import LLMConfigurationError, LLMPolicy, ModelAdapter, OpenAICompatibleModelAdapter
from .rules import _validate_action, finish_draw, initial_game
from .schemas import Action, GameState, Phase, Role
from .storage import ArtifactStore, RequestTraceStore
from .visibility import discussion_order, observation_for


HTML_PATH = Path(__file__).with_name("web.html")
PLAYER_HTML_PATH = Path(__file__).with_name("player.html")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RoomConflictError(Exception):
    """服务实例已有一个仍在运行的房间。"""


class RoomNotFoundError(Exception):
    """请求的房间不存在。"""


class InvalidCursorError(ValueError):
    """事件增量游标不是非负整数。"""


class PlayerAuthenticationError(Exception):
    """玩家会话令牌无效或缺失。"""


class PlayerSessionConflictError(Exception):
    """房间已经绑定了一个玩家座位或重复绑定。"""


class PlayerNotReadyError(Exception):
    """当前还没有轮到玩家提交行动。"""


class InvalidPlayerActionError(ValueError):
    """玩家 Action 不符合当前阶段的规则。"""


class HumanPolicy:
    """把 Web 玩家 Action 转换成阻塞中的 Policy 决策。"""

    def __init__(self, player_id: str):
        self.player_id = player_id
        self._condition = threading.Condition()
        self._waiting = False
        self._observation = None
        self._action: Action | None = None
        self._cancelled = False

    @property
    def waiting(self) -> bool:
        with self._condition:
            return self._waiting and not self._cancelled

    def decide(self, observation):
        with self._condition:
            self._observation = observation
            self._waiting = True
            self._condition.notify_all()
            while self._action is None and not self._cancelled:
                self._condition.wait()
            action = self._action or Action(actor_id=self.player_id, action_type="noop")
            self._action = None
            self._observation = None
            self._waiting = False
            return action

    def submit(self, action: Action) -> None:
        with self._condition:
            if self._cancelled or not self._waiting:
                raise PlayerNotReadyError("player is not waiting for an action")
            if self._action is not None:
                raise PlayerSessionConflictError("player action already submitted")
            self._action = action
            self._condition.notify_all()

    def cancel(self) -> None:
        with self._condition:
            self._cancelled = True
            self._condition.notify_all()


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
        run_dir: Path | None = None,
    ):
        self.state = state
        self.engine = GameEngine(seed=state.seed, policies=policies)
        self.step_interval = max(0.0, float(step_interval))
        self.max_rounds = max(1, int(max_rounds))
        self.policy_mode = policy_mode
        self.model_name = model_name
        self.pricing_configured = pricing_configured
        self.request_collector = request_collector or RequestTraceCollector()
        self.run_dir = run_dir
        self.artifacts: dict[str, str] = {}
        self._state_lock = threading.RLock()
        self._step_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.worker_error: str | None = None
        self.human_player_id: str | None = None
        self.human_policy: HumanPolicy | None = None
        self._in_flight_player_id: str | None = None
        self._in_flight_phase: Phase | None = None
        self._in_flight_state: GameState | None = None
        self._session_tokens: dict[str, str] = {}
        self._session_by_player: dict[str, str] = {}

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
                try:
                    next_state = self.engine.step(
                        current_state,
                        on_actor_start=self._mark_in_flight_actor,
                        on_actor_complete=self._update_in_flight_state,
                    )
                except Exception:
                    self._clear_in_flight_actor()
                    raise
            with self._state_lock:
                self.state = next_state
                self._in_flight_player_id = None
                self._in_flight_phase = None
                self._in_flight_state = None
            self._persist()
            if next_state.status != "RUNNING":
                self._done_event.set()
            return next_state

    def _mark_in_flight_actor(self, state: GameState, player_id: str) -> None:
        """记录阶段内当前正在等待 Policy 返回的玩家，供玩家接口实时显示。"""
        with self._state_lock:
            self._in_flight_player_id = player_id
            self._in_flight_phase = state.phase
            self._in_flight_state = state

    def _update_in_flight_state(self, state: GameState, _player_id: str) -> None:
        """保存当前阶段已完成行动的临时状态，让前序公开事件即时可见。"""
        with self._state_lock:
            if self._in_flight_phase == state.phase:
                self._in_flight_state = state

    def _clear_in_flight_actor(self) -> None:
        """阶段结算或异常后清理进行中玩家，避免下一阶段读取旧值。"""
        with self._state_lock:
            self._in_flight_player_id = None
            self._in_flight_phase = None
            self._in_flight_state = None

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

    def create_player_session(self, player_id: str) -> str:
        """创建本地开发座位会话，并把该座位切换为 HumanPolicy。"""
        with self._state_lock:
            if self.state.status != "RUNNING" or (self._thread and self._thread.is_alive()):
                raise PlayerSessionConflictError("room is already running")
            if not any(player.player_id == player_id for player in self.state.players):
                raise PlayerAuthenticationError("unknown player")
            if self.human_player_id is not None or player_id in self._session_by_player:
                raise PlayerSessionConflictError("room already has a local player seat")
            policy = HumanPolicy(player_id)
            self.human_player_id = player_id
            self.human_policy = policy
            self.engine.policies[player_id] = policy
            token = secrets.token_urlsafe(24)
            self._session_tokens[token] = player_id
            self._session_by_player[player_id] = token
            return token

    def _player_for_token(self, token: str | None) -> str:
        if not token:
            raise PlayerAuthenticationError("player session token is required")
        with self._state_lock:
            player_id = self._session_tokens.get(token)
        if player_id is None:
            raise PlayerAuthenticationError("invalid player session token")
        return player_id

    def _active_player(self, state: GameState) -> str | None:
        actors = self.engine._actors_for_phase(state)
        pending = {action.actor_id for action in state.pending_actions}
        return next((actor for actor in actors if actor not in pending), None)

    @staticmethod
    def _allowed_actions(state: GameState, player_id: str) -> list[str]:
        player = next(item for item in state.players if item.player_id == player_id)
        if not player.alive:
            return []
        allowed = {
            Phase.NIGHT_WOLF: ["wolf_speak", "noop"] if player.role == Role.WOLF else [],
            Phase.NIGHT_WOLF_CONFIRM: ["wolf_vote", "noop"] if player.role == Role.WOLF else [],
            Phase.NIGHT_SEER: ["inspect", "noop"] if player.role == Role.SEER else [],
            Phase.NIGHT_WITCH: ["witch_save", "witch_poison", "noop"] if player.role == Role.WITCH else [],
            Phase.DAY_DISCUSSION: ["speak"],
            Phase.DAY_VOTE: ["vote", "abstain"],
        }.get(state.phase, [])
        if state.phase == Phase.NIGHT_WITCH and state.night_victim is None:
            allowed = [action for action in allowed if action != "witch_save"]
        return allowed

    def player_snapshot(self, token: str | None, after: int = 0) -> dict[str, Any]:
        """返回单个玩家的授权视图，不包含完整玩家列表或待结算 Action。"""
        if after < 0:
            raise InvalidCursorError("after must be a non-negative integer")
        player_id = self._player_for_token(token)
        with self._state_lock:
            state = self._in_flight_state or self.state
            human_policy = self.human_policy
            active_player_id = (
                self._in_flight_player_id
                if self._in_flight_phase == state.phase
                else self._active_player(state)
            )
            player = next(item for item in state.players if item.player_id == player_id)
            authorized_events = [
                event for event in state.events[after:]
                if event.public or player_id in event.recipients
            ]
            player_events = []
            for event in authorized_events:
                if event.public:
                    player_events.append(event.to_dict())
                else:
                    player_events.append(
                        {
                            "event_id": event.event_id,
                            "round_number": event.round_number,
                            "phase": event.phase.value,
                            "event_type": event.event_type,
                            "payload": event.payload,
                            "public": False,
                        }
                    )
            observation = observation_for(state, player_id)
            private = observation.private
            is_waiting = bool(human_policy and human_policy.waiting and active_player_id == player_id)
            return {
                "game_id": state.game_id,
                "player": {
                    "player_id": player.player_id,
                    "role": player.role.value,
                    "alive": player.alive,
                    "antidote_available": player.antidote_available,
                    "poison_available": player.poison_available,
                    "wolf_teammates": list(private.get("wolf_teammates", [])),
                    "inspection_results": list(private.get("inspection_results", [])),
                    "night_victim": private.get("night_victim"),
                },
                "phase": state.phase.value,
                "round_number": state.round_number,
                "status": state.status,
                "winner": state.winner,
                "alive_players": [item.player_id for item in state.players if item.alive],
                "discussion_order": discussion_order(state) if state.phase == Phase.DAY_DISCUSSION else [],
                "active_player_id": active_player_id,
                "can_act": is_waiting,
                "allowed_actions": self._allowed_actions(state, player_id) if is_waiting else [],
                "events": player_events,
                "cursor": len(state.events),
            }

    def submit_player_action(self, token: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        """校验并排队一个玩家 Action；规则引擎仍负责最终结算。"""
        player_id = self._player_for_token(token)
        action_type = payload.get("action_type")
        target_id = payload.get("target_id")
        speech = payload.get("speech", "")
        decision_label = payload.get("decision_label", "")
        if not isinstance(action_type, str) or not action_type:
            raise InvalidPlayerActionError("action_type is required")
        if target_id is not None and not isinstance(target_id, str):
            raise InvalidPlayerActionError("target_id must be a string or null")
        if not isinstance(speech, str) or not isinstance(decision_label, str):
            raise InvalidPlayerActionError("speech and decision_label must be strings")
        if len(speech) > 240 or len(decision_label) > 80:
            raise InvalidPlayerActionError("speech or decision_label is too long")
        action = Action(
            actor_id=player_id,
            action_type=action_type,
            target_id=target_id,
            speech=speech,
            decision_label=decision_label,
        )
        with self._state_lock:
            state = self.state
            policy = self.human_policy
        if policy is None or self.human_player_id != player_id:
            raise PlayerAuthenticationError("player seat is not attached to this room")
        reason = _validate_action(state, action)
        if reason:
            raise InvalidPlayerActionError(reason)
        policy.submit(action)
        return {
            "accepted": True,
            "game_id": state.game_id,
            "player_id": player_id,
            "phase": state.phase.value,
        }

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
                try:
                    self._persist()
                except Exception:
                    pass

    def _persist(self) -> None:
        if self.run_dir is None:
            return
        with self._state_lock:
            state = self.state
        report = evaluate_game(state, offline=self.policy_mode != "llm")
        artifact_paths = ArtifactStore(self.run_dir).write(state, report, god_view=True)
        self.artifacts = {
            "run_dir": str(self.run_dir),
            **artifact_paths,
        }

    def stop(self) -> None:
        if self.human_policy is not None:
            self.human_policy.cancel()
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
            "artifacts": dict(self.artifacts),
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
        output_root: Path | None = None,
    ):
        if policy_mode not in {"rule", "llm"}:
            raise ValueError("policy_mode must be rule or llm")
        self.step_interval = step_interval
        self.max_rounds = max_rounds
        self.default_seed = default_seed
        self.policy_mode = policy_mode
        self.model_adapter = model_adapter
        self.output_root = Path(output_root) if output_root is not None else None
        self._lock = threading.RLock()
        self._room: Room | None = None

    def create(self, seed: int | None = None) -> Room:
        with self._lock:
            if self._room is not None and self._room.state.status == "RUNNING":
                raise RoomConflictError("an active room already exists")
            if self._room is not None:
                self._room.stop()
            state = initial_game(self.default_seed if seed is None else seed)
            run_dir = None
            if self.output_root is not None:
                run_dir = ArtifactStore.default_run_directory(self.output_root, state.seed)
            collector = RequestTraceCollector(run_dir / "llm_requests.jsonl" if run_dir else None)
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
                run_dir=run_dir,
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
            "seats": [player.player_id for player in state.players],
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


def make_handler(
    store: RoomStore,
    html_path: Path = HTML_PATH,
    player_html_path: Path = PLAYER_HTML_PATH,
):
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

        def _bearer_token(self) -> str | None:
            value = self.headers.get("Authorization", "")
            prefix = "Bearer "
            return value[len(prefix):].strip() if value.startswith(prefix) else None

        def _send_html(self, path: Path) -> None:
            body = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _room_route(self, path: list[str]) -> tuple[Room, str] | None:
            if len(path) != 4 or path[:2] != ["api", "rooms"]:
                return None
            return store.get(path[2]), path[3]

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/player"}:
                try:
                    self._send_html(html_path if parsed.path == "/" else player_html_path)
                except OSError:
                    self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "page_unavailable", "audit page is unavailable")
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
                if route is None or route[1] not in {"audit", "public", "player"}:
                    self._send_error(HTTPStatus.NOT_FOUND, "not_found", "route not found")
                    return
                room, view = route
                query = parse_qs(parsed.query)
                after = _cursor(query, "after")
                if view == "audit":
                    request_after = _cursor(query, "request_after")
                    self._send_json(room.snapshot(after, request_after))
                elif view == "public":
                    self._send_json(public_snapshot(room, after))
                else:
                    self._send_json(room.player_snapshot(self._bearer_token(), after))
            except RoomNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "room_not_found", "room not found")
            except InvalidCursorError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid_cursor", str(exc))
            except PlayerAuthenticationError as exc:
                self._send_error(HTTPStatus.UNAUTHORIZED, "player_unauthorized", str(exc))
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
                if len(path) == 4 and path[:2] == ["api", "rooms"] and path[3] == "sessions":
                    room = store.get(path[2])
                    body = self._body()
                    player_id = body.get("player_id")
                    if not isinstance(player_id, str) or not player_id:
                        raise ValueError("player_id must be a non-empty string")
                    token = room.create_player_session(player_id)
                    self._send_json(
                        {"game_id": room.game_id, "player_id": player_id, "token": token, "mode": "local_player"},
                        HTTPStatus.CREATED,
                    )
                    return
                if len(path) == 4 and path[:2] == ["api", "rooms"] and path[3] == "actions":
                    room = store.get(path[2])
                    result = room.submit_player_action(self._bearer_token(), self._body())
                    self._send_json(result, HTTPStatus.ACCEPTED)
                    return
                if len(path) == 4 and path[:2] == ["api", "rooms"] and path[3] == "start":
                    room = store.get(path[2])
                    room.start()
                    self._send_json(_summary(room))
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "not_found", "route not found")
            except RoomConflictError:
                self._send_error(HTTPStatus.CONFLICT, "room_conflict", "an active room already exists")
            except PlayerSessionConflictError as exc:
                self._send_error(HTTPStatus.CONFLICT, "player_session_conflict", str(exc))
            except PlayerNotReadyError as exc:
                self._send_error(HTTPStatus.CONFLICT, "player_not_ready", str(exc))
            except PlayerAuthenticationError as exc:
                self._send_error(HTTPStatus.UNAUTHORIZED, "player_unauthorized", str(exc))
            except InvalidPlayerActionError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, "invalid_player_action", str(exc))
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
    parser.add_argument("--max-rounds", type=int, default=4)
    parser.add_argument("--step-interval", type=float, default=0.5)
    parser.add_argument("--policy", choices=("rule", "llm"), default="rule")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()
    model_adapter = None
    if args.policy == "llm":
        try:
            model_adapter = OpenAICompatibleModelAdapter.from_environment()
        except LLMConfigurationError as error:
            parser.error(str(error))
    store = RoomStore(
        step_interval=args.step_interval,
        max_rounds=args.max_rounds,
        default_seed=args.seed,
        policy_mode=args.policy,
        model_adapter=model_adapter,
        output_root=args.output_root,
    )
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

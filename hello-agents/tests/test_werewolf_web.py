import json
import os
import sys
import subprocess
from types import SimpleNamespace
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "16-graduation-project"
WEB_HTML = PROJECT / "werewolf_arena" / "web.html"
sys.path.insert(0, str(PROJECT))

from werewolf_arena.engine import GameEngine
from werewolf_arena.policies import ScriptedModelAdapter
from werewolf_arena.rules import initial_game
from werewolf_arena.schemas import Phase
from werewolf_arena.web import RoomConflictError, RoomStore, build_server

if str(PROJECT) in sys.path:
    sys.path.remove(str(PROJECT))


class WerewolfWebTests(unittest.TestCase):
    """覆盖 Web 垂直切片依赖的引擎和本地服务契约。"""

    def setUp(self):
        self.http_store = RoomStore(step_interval=60.0)
        self.http_server = build_server("127.0.0.1", 0, store=self.http_store)
        self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
        self.http_thread.start()
        self.base_url = f"http://127.0.0.1:{self.http_server.server_port}"
        self.addCleanup(self._close_http)

    def _close_http(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        self.http_store.close()
        self.http_thread.join(timeout=1.0)

    def request_json(self, method, path, payload=None, expect_error=False):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urlopen(request, timeout=2.0) as response:
                result = SimpleNamespace(status=response.status, payload=json.loads(response.read().decode("utf-8")))
        except HTTPError as error:
            result = SimpleNamespace(status=error.code, payload=json.loads(error.read().decode("utf-8")))
        if not expect_error:
            self.assertLess(result.status, 400)
        return result

    def test_step_advances_one_phase_without_running_to_completion(self):
        state = initial_game(seed=7)
        stepped = GameEngine(seed=7).step(state)

        self.assertEqual(stepped.phase, Phase.NIGHT_WOLF_CONFIRM)
        self.assertEqual(stepped.round_number, 1)
        self.assertEqual(stepped.status, "RUNNING")
        self.assertNotEqual(stepped, state)

    def test_room_store_creates_one_room_and_rejects_second_active_room(self):
        store = RoomStore(step_interval=0.001)
        first = store.create(seed=7)
        self.assertEqual(first.state.phase, Phase.NIGHT_WOLF)

        with self.assertRaises(RoomConflictError):
            store.create(seed=18)

        store.close()

    def test_room_step_once_returns_incremental_snapshot(self):
        store = RoomStore(step_interval=0.001)
        room = store.create(seed=7)

        before = room.snapshot(after=0)
        room.step_once()
        after = room.snapshot(after=0)

        self.assertEqual(before["cursor"], 0)
        self.assertGreater(after["cursor"], before["cursor"])
        self.assertEqual(after["state"]["phase"], "night_wolf_confirm")
        store.close()

    def test_room_worker_reaches_terminal_state(self):
        store = RoomStore(step_interval=0.001, max_rounds=4)
        room = store.create(seed=7)
        room.start()

        self.assertTrue(room.wait_until_done(timeout=2.0))
        self.assertIn(room.snapshot(after=0)["state"]["status"], {"COMPLETED", "DRAW"})
        store.close()

    def test_llm_room_creates_six_policies_and_collects_redacted_requests(self):
        adapter = ScriptedModelAdapter(['{"action_type": "noop"}'])
        store = RoomStore(policy_mode="llm", model_adapter=adapter, step_interval=60.0)
        room = store.create(seed=7)

        room.step_once()
        snapshot = room.snapshot(after=0, request_after=0)

        self.assertEqual(snapshot["policy_mode"], "llm")
        self.assertEqual(len(adapter.calls), 2)
        self.assertEqual(snapshot["request_cursor"], 2)
        self.assertEqual(len(snapshot["llm_requests"]), 2)
        self.assertNotIn("Prompt", json.dumps(snapshot["llm_requests"]))
        self.assertNotIn('{"action_type": "noop"}', json.dumps(snapshot["llm_requests"]))
        store.close()

    def test_http_create_start_and_incremental_audit(self):
        created = self.request_json("POST", "/api/rooms", {"seed": 7})
        self.assertEqual(created.status, 201)
        game_id = created.payload["game_id"]

        room = self.http_store.get(game_id)
        room.step_once()
        started = self.request_json("POST", f"/api/rooms/{game_id}/start", {})
        self.assertEqual(started.status, 200)

        audit = self.request_json("GET", f"/api/rooms/{game_id}/audit?after=0")
        self.assertEqual(audit.payload["state"]["phase"], "night_wolf_confirm")
        self.assertEqual(audit.payload["cursor"], len(audit.payload["state"]["events"]))
        self.assertGreaterEqual(len(audit.payload["events"]), 1)

    def test_public_endpoint_omits_private_identity_and_events(self):
        created = self.request_json("POST", "/api/rooms", {"seed": 7})
        game_id = created.payload["game_id"]
        room = self.http_store.get(game_id)
        room.step_once()

        public = self.request_json("GET", f"/api/rooms/{game_id}/public?after=0")
        body = json.dumps(public.payload, ensure_ascii=False)
        self.assertNotIn('"role"', body)
        self.assertNotIn('"pending_actions"', body)
        self.assertNotIn('"public": false', body)

    def test_http_errors_are_stable_json(self):
        response = self.request_json("GET", "/api/rooms/missing/audit", expect_error=True)
        self.assertEqual(response.status, 404)
        self.assertEqual(response.payload["error"], "room_not_found")

    def test_audit_page_contains_timeline_and_polling_contract(self):
        html = WEB_HTML.read_text(encoding="utf-8")
        for marker in (
            "上帝视角",
            "开发 / 裁判回放",
            "/api/rooms",
            "/audit?after=",
            "事件时间线",
            "事件详情",
            "状态快照",
            "setInterval",
        ):
            self.assertIn(marker, html)

    def test_web_module_starts_local_server(self):
        environment = dict(os.environ)
        process = subprocess.Popen(
            [sys.executable, "-m", "werewolf_arena.web", "--port", "0", "--step-interval", "60"],
            cwd=PROJECT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        try:
            line = process.stdout.readline().strip()
            self.assertIn("http://127.0.0.1:", line)
            self.assertIn("/", line)
        finally:
            process.terminate()
            process.wait(timeout=2)
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

import sys
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "16-graduation-project"
sys.path.insert(0, str(PROJECT))

from werewolf_arena.engine import GameEngine
from werewolf_arena.rules import initial_game
from werewolf_arena.schemas import Phase
from werewolf_arena.web import RoomConflictError, RoomStore

if str(PROJECT) in sys.path:
    sys.path.remove(str(PROJECT))


class WerewolfWebTests(unittest.TestCase):
    """覆盖 Web 垂直切片依赖的引擎和本地服务契约。"""

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

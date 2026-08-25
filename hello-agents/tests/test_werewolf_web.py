import sys
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "16-graduation-project"
sys.path.insert(0, str(PROJECT))

from werewolf_arena.engine import GameEngine
from werewolf_arena.rules import initial_game
from werewolf_arena.schemas import Phase

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

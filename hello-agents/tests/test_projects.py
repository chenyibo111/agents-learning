import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectRuntimeTests(unittest.TestCase):
    def test_every_project_runs_offline_demo(self):
        for main_file in sorted((ROOT / "projects").glob("[0-9][0-9]-*/main.py")):
            completed = subprocess.run(
                [sys.executable, str(main_file), "--demo"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(completed.returncode, 0, f"{main_file}: {completed.stderr}")
            self.assertTrue(completed.stdout.strip(), main_file)

    def test_bounded_loop_rejects_invalid_limit(self):
        sys.path.insert(0, str(ROOT / "projects"))
        from common.agent_loop import run_loop

        with self.assertRaises(ValueError):
            run_loop({}, lambda state: None, lambda state, action: (state, None), lambda state: True, max_steps=0)


if __name__ == "__main__":
    unittest.main()

import json
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "16-graduation-project"
sys.path.insert(0, str(PROJECT))

from werewolf_arena.engine import GameEngine
from werewolf_arena.evaluation import evaluate_game
from werewolf_arena.policies import LLMConfigurationError, LLMPolicy, OpenAICompatibleModelAdapter, ScriptedModelAdapter
from werewolf_arena.rules import advance_phase, initial_game, submit_action
from werewolf_arena.schemas import Action, Phase, Role
from werewolf_arena.storage import ArtifactStore
from werewolf_arena.visibility import observation_for


def player_id(state, role):
    """测试辅助函数：按身份取出该局对应的玩家 ID，避免依赖随机分配顺序。"""
    return next(player.player_id for player in state.players if player.role == role)


def alive_ids(state):
    """测试辅助函数：返回当前仍可行动的玩家 ID。"""
    return [player.player_id for player in state.players if player.alive]


class WerewolfArenaTests(unittest.TestCase):
    """覆盖角色、信息边界、规则、模型降级、恢复和 CLI 的离线集成测试。"""

    def test_seeded_game_has_six_required_roles(self):
        """同 seed 必须得到同样的六角色构成和初始状态。"""
        state = initial_game(seed=17)
        self.assertEqual(6, len(state.players))
        self.assertEqual(
            Counter({Role.WOLF: 2, Role.SEER: 1, Role.WITCH: 1, Role.VILLAGER: 2}),
            Counter(player.role for player in state.players),
        )
        self.assertEqual(initial_game(seed=17).to_dict(), state.to_dict())

    def test_visibility_hides_every_other_private_role_and_resource(self):
        """村民和狼人只能得到其身份允许的私有信息。"""
        state = initial_game(seed=7)
        villager = player_id(state, Role.VILLAGER)
        villager_view = observation_for(state, villager).to_dict()
        self.assertEqual(Role.VILLAGER.value, villager_view["private"]["role"])
        self.assertNotIn("wolf_teammates", villager_view["private"])
        self.assertNotIn("inspection_results", villager_view["private"])
        self.assertNotIn("antidote_available", villager_view["private"])
        self.assertNotIn(Role.WOLF.value, json.dumps(villager_view["private"], ensure_ascii=False))

        wolf = player_id(state, Role.WOLF)
        wolf_view = observation_for(state, wolf).to_dict()
        self.assertEqual(1, len(wolf_view["private"]["wolf_teammates"]))
        self.assertNotIn("inspection_results", wolf_view["private"])

    def test_illegal_night_action_is_rejected_without_changing_pending_actions(self):
        """村民冒充狼人时，环境必须拒绝且不能污染待结算行动。"""
        state = initial_game(seed=7)
        villager = player_id(state, Role.VILLAGER)
        target = next(item for item in alive_ids(state) if item != villager)
        rejected = submit_action(state, Action(villager, "wolf_kill", target))
        self.assertEqual((), rejected.pending_actions)
        self.assertEqual("action_rejected", rejected.events[-1].event_type)
        self.assertEqual("role_cannot_act", rejected.events[-1].rule)

    def test_matched_wolf_attack_can_be_saved_by_witch(self):
        """两狼一致目标可被女巫获知并使用解药救下。"""
        state = initial_game(seed=7)
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        witch = player_id(state, Role.WITCH)
        victim = next(item for item in alive_ids(state) if item not in wolves and item != witch)
        for wolf in wolves:
            state = submit_action(state, Action(wolf, "wolf_kill", victim))
        state = advance_phase(state)
        self.assertEqual(Phase.NIGHT_SEER, state.phase)
        self.assertEqual(Phase.NIGHT_WOLF, state.events[-1].phase)
        seer = player_id(state, Role.SEER)
        state = submit_action(state, Action(seer, "inspect", wolves[0]))
        state = advance_phase(state)
        self.assertEqual(Phase.NIGHT_WITCH, state.phase)
        witch_view = observation_for(state, witch)
        self.assertEqual(victim, witch_view.private["night_victim"])
        state = submit_action(state, Action(witch, "witch_save", victim))
        state = advance_phase(state)
        self.assertTrue(next(player for player in state.players if player.player_id == victim).alive)
        self.assertFalse(next(player for player in state.players if player.player_id == witch).antidote_available)
        self.assertIn("night_saved", [event.event_type for event in state.events])

    def test_tied_day_votes_do_not_execute_any_player(self):
        """最高票并列时不能由引擎任意选择一名玩家出局。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        ids = alive_ids(state)
        for voter, target in zip(ids, [ids[1], ids[0], ids[3], ids[2], ids[5], ids[4]], strict=True):
            state = submit_action(state, Action(voter, "vote", target))
        resolved = advance_phase(state)
        self.assertTrue(all(player.alive for player in resolved.players))
        self.assertEqual("vote_tied", resolved.events[-1].event_type)

    def test_llm_policy_falls_back_to_noop_for_invalid_json(self):
        """模型输出格式错误时应安全降级，不让自然语言直接影响规则。"""
        state = initial_game(seed=7)
        player = player_id(state, Role.WOLF)
        adapter = ScriptedModelAdapter(["这不是 JSON"])
        action = LLMPolicy(player, adapter).decide(observation_for(state, player))
        self.assertEqual("noop", action.action_type)
        self.assertEqual(player, action.actor_id)
        self.assertEqual(1, action.model_calls)

    def test_live_model_adapter_requires_endpoint_and_secret(self):
        """真实模型缺少 endpoint、密钥或模型名时应明确拒绝启动。"""
        with self.assertRaises(LLMConfigurationError):
            OpenAICompatibleModelAdapter(endpoint="", api_key="", model="")

    def test_full_rule_game_ends_with_winner_or_draw(self):
        """不依赖真实模型的规则局必须在轮数上限内终止。"""
        state = GameEngine(seed=7).run(max_rounds=3)
        self.assertIn(state.status, {"COMPLETED", "DRAW"})
        self.assertTrue(state.events)
        self.assertGreaterEqual(state.round_number, 1)

    def test_checkpoint_resume_matches_continuous_game(self):
        """中断恢复不得重复或遗漏事件，应与连续运行完全一致。"""
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            interrupted = GameEngine(seed=7).run(
                max_rounds=3,
                interrupt_after_phase=Phase.NIGHT_SEER,
                checkpoint_path=checkpoint,
            )
            resumed = GameEngine.resume(checkpoint, max_rounds=3)
        continuous = GameEngine(seed=7).run(max_rounds=3)
        self.assertEqual("INTERRUPTED", interrupted.status)
        self.assertEqual(continuous.to_dict(), resumed.to_dict())

    def test_evaluation_audits_public_events_and_reports_metrics(self):
        """评测报告必须同时包含胜负、隐私审计和模型指标字段。"""
        state = GameEngine(seed=7).run(max_rounds=2)
        report = evaluate_game(state)
        self.assertIn(report["winner"], {"wolves", "good", "draw"})
        self.assertTrue(report["privacy_audit"]["passed"])
        self.assertIn("model_calls", report["metrics"])

    def test_cli_writes_json_report_and_trace(self):
        """显式输出目录时 CLI 要写出 checkpoint、JSONL 和报告三个工件。"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--json",
                    "--seed",
                    "7",
                    "--max-rounds",
                    "2",
                    "--output-dir",
                    directory,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertIn(payload["state"]["status"], {"COMPLETED", "DRAW"})
            self.assertTrue((Path(directory) / "checkpoint.json").exists())
            self.assertTrue((Path(directory) / "events.jsonl").exists())
            self.assertTrue((Path(directory) / "report.json").exists())

    def test_default_run_directory_is_unique_and_stays_under_project_runs(self):
        """未指定目录的新对局应默认归档在项目 runs 下，并避免覆盖其他 seed。"""
        fixed_time = datetime(2026, 8, 25, 12, 30, 45, 123456)
        root = PROJECT
        first = ArtifactStore.default_run_directory(root, seed=7, now=fixed_time)
        second = ArtifactStore.default_run_directory(root, seed=8, now=fixed_time)
        self.assertEqual(root / "runs", first.parent)
        self.assertIn("seed-7", first.name)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()

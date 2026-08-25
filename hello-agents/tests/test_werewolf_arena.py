import json
from collections import Counter
from dataclasses import replace
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "16-graduation-project"
sys.path.insert(0, str(PROJECT))

from werewolf_arena.engine import GameEngine
from werewolf_arena.evaluation import evaluate_game
from werewolf_arena.policies import LLMConfigurationError, LLMPolicy, ModelResponse, OpenAICompatibleModelAdapter, ScriptedModelAdapter
from werewolf_arena.rules import advance_phase, initial_game, submit_action
from werewolf_arena.schemas import Action, Event, Phase, Role
from werewolf_arena.god_view import render_god_view_html
from werewolf_arena.narrative import render_public_events
from werewolf_arena.spectator import render_spectator_html
from werewolf_arena.storage import ArtifactStore, RequestTraceStore
from werewolf_arena.visibility import model_prompts, observation_for

if str(PROJECT) in sys.path:
    sys.path.remove(str(PROJECT))


def player_id(state, role):
    """测试辅助函数：按身份取出该局对应的玩家 ID，避免依赖随机分配顺序。"""
    return next(player.player_id for player in state.players if player.role == role)


def alive_ids(state):
    """测试辅助函数：返回当前仍可行动的玩家 ID。"""
    return [player.player_id for player in state.players if player.alive]


def expected_discussion_order(state):
    """测试辅助函数：按固定座位和轮次计算期望的轮换发言顺序。"""
    seats = [player.player_id for player in state.players]
    start = (state.round_number - 1) % len(seats)
    rotated = seats[start:] + seats[:start]
    alive = set(alive_ids(state))
    return [player_id for player_id in rotated if player_id in alive]


class FakeHTTPResponse:
    """用于适配器契约测试的最小 urllib 响应替身。"""

    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


class WerewolfArenaTests(unittest.TestCase):
    """覆盖角色、信息边界、规则、模型降级、恢复和 CLI 的离线集成测试。"""

    def _advance_wolves_to_confirm_phase(self, seed=7):
        """测试辅助函数：提交两名狼人的私密建议并进入确认投票阶段。"""
        state = initial_game(seed=seed)
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        for wolf in wolves:
            state = submit_action(state, Action(wolf, "wolf_speak", speech="先观察公开票型，再统一确认目标。"))
        return advance_phase(state)

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

    def test_wolves_negotiate_in_private_before_confirming_target(self):
        """狼人先私密发言，发言只对狼人可见，然后进入确认投票阶段。"""
        state = initial_game(seed=7)
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]

        state = submit_action(state, Action(wolves[0], "wolf_speak", speech="先观察票型。"))

        self.assertNotIn("wolf_negotiation_message", [event.event_type for event in state.events if event.public])
        wolf_view = observation_for(state, wolves[1])
        self.assertIn("先观察票型。", json.dumps(wolf_view.private["private_events"], ensure_ascii=False))
        villager_view = observation_for(state, player_id(state, Role.VILLAGER))
        self.assertNotIn("先观察票型。", json.dumps(villager_view.to_dict(), ensure_ascii=False))

        state = submit_action(state, Action(wolves[1], "wolf_speak", speech="确认后投同一个目标。"))
        state = advance_phase(state)

        self.assertEqual(Phase.NIGHT_WOLF_CONFIRM, state.phase)

    def test_wolf_confirm_votes_are_hidden_and_consensus_forms_attack(self):
        """狼人确认票在双方提交前隐藏，同目标才形成袭击。"""
        state = self._advance_wolves_to_confirm_phase()
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        target = next(player.player_id for player in state.players if player.role != Role.WOLF)

        state = submit_action(state, Action(wolves[0], "wolf_vote", target))
        self.assertNotIn("wolf_vote_revealed", [event.event_type for event in state.events])
        state = submit_action(state, Action(wolves[1], "wolf_vote", target))
        state = advance_phase(state)

        reveal = next(event for event in state.events if event.event_type == "wolf_vote_revealed")
        self.assertFalse(reveal.public)
        self.assertEqual(target, state.night_victim)
        self.assertEqual(Phase.NIGHT_SEER, state.phase)

    def test_wolf_confirm_split_votes_create_no_attack(self):
        """狼人确认票分歧时不形成袭击。"""
        state = self._advance_wolves_to_confirm_phase()
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        targets = [player.player_id for player in state.players if player.role != Role.WOLF]

        state = submit_action(state, Action(wolves[0], "wolf_vote", targets[0]))
        state = submit_action(state, Action(wolves[1], "wolf_vote", targets[1]))
        state = advance_phase(state)

        self.assertIsNone(state.night_victim)
        self.assertEqual("wolf_attack_failed", state.events[-1].event_type)

    def test_rule_policy_runs_wolf_talk_then_confirm_vote(self):
        """离线策略必须实际经历狼人私聊和确认投票两个阶段。"""
        state = GameEngine(seed=7).run(max_rounds=1)

        wolf_messages = [event for event in state.events if event.event_type == "wolf_negotiation_message"]
        wolf_votes = [event for event in state.events if event.event_type == "wolf_vote_revealed"]

        self.assertGreaterEqual(len(wolf_messages), 2)
        self.assertGreaterEqual(len(wolf_votes), 1)

    def test_model_prompt_declares_wolf_talk_and_confirm_protocol(self):
        """Prompt 必须区分狼人私聊和隐藏确认票。"""
        state = initial_game(seed=7)
        wolf = player_id(state, Role.WOLF)
        talk_system, _ = model_prompts(observation_for(state, wolf))
        confirm_state = replace(state, phase=Phase.NIGHT_WOLF_CONFIRM)
        confirm_system, _ = model_prompts(observation_for(confirm_state, wolf))

        self.assertIn("wolf_speak", talk_system)
        self.assertIn("私密", talk_system)
        self.assertIn("wolf_vote", confirm_system)
        self.assertIn("看不到队友的确认票", confirm_system)

    def test_witch_cannot_save_when_wolves_fail_to_form_an_attack(self):
        """没有夜袭目标时，女巫救药必须被拒绝且不能消耗解药。"""
        state = initial_game(seed=7)
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        witch = player_id(state, Role.WITCH)
        for wolf in wolves:
            state = submit_action(state, Action(wolf, "noop"))
        state = advance_phase(state)
        for wolf in wolves:
            state = submit_action(state, Action(wolf, "noop"))
        state = advance_phase(state)
        seer = player_id(state, Role.SEER)
        state = submit_action(state, Action(seer, "noop"))
        state = advance_phase(state)

        rejected = submit_action(state, Action(witch, "witch_save", None))

        self.assertEqual((), rejected.pending_actions)
        self.assertEqual("action_rejected", rejected.events[-1].event_type)
        self.assertEqual("no_attack_to_save", rejected.events[-1].rule)
        resolved = advance_phase(rejected)
        witch_state = next(player for player in resolved.players if player.player_id == witch)
        self.assertTrue(witch_state.antidote_available)
        self.assertNotIn("night_saved", [event.event_type for event in resolved.events])

    def test_votes_are_hidden_until_all_players_finish_voting_then_revealed(self):
        """投票期间不公开前序票型，全部提交后一次性公开个人票型和总票数。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        ids = alive_ids(state)
        first_target = ids[1]
        state = submit_action(state, Action(ids[0], "vote", first_target))
        self.assertNotIn("vote_cast", [event.event_type for event in state.events])
        next_view = observation_for(state, ids[1])
        self.assertNotIn("vote_cast", [event["event_type"] for event in next_view.public["events"]])

        targets = [ids[1], ids[0], ids[1], ids[1], ids[1], ids[1]]
        for voter, target in zip(ids[1:], targets[1:], strict=True):
            state = submit_action(state, Action(voter, "vote", target))
        resolved = advance_phase(state)
        reveal = next(event for event in resolved.events if event.event_type == "vote_revealed")

        self.assertEqual(first_target, reveal.payload["ballots"][ids[0]])
        self.assertEqual(5, reveal.payload["counts"][first_target])
        self.assertEqual(6, len(reveal.payload["ballots"]))
        self.assertEqual(6, evaluate_game(resolved)["vote_count"])

    def test_discussion_order_rotates_by_round_and_skips_dead_players(self):
        """发言首位按固定座位轮换，死亡玩家从当轮顺序中跳过。"""
        initial = initial_game(seed=7)
        ids = alive_ids(initial)
        self.assertEqual(ids, expected_discussion_order(replace(initial, phase=Phase.DAY_DISCUSSION, round_number=1)))
        self.assertEqual(ids[1:] + ids[:1], expected_discussion_order(replace(initial, phase=Phase.DAY_DISCUSSION, round_number=2)))

        players = tuple(
            replace(player, alive=False) if player.player_id == ids[1] else player
            for player in initial.players
        )
        state = replace(initial, players=players, phase=Phase.DAY_DISCUSSION, round_number=2)
        self.assertEqual(ids[2:] + ids[:1], expected_discussion_order(state))

    def test_observation_and_prompt_expose_discussion_order_and_hidden_vote_rule(self):
        """玩家视图和模型协议必须说明发言顺序及投票期间的隐藏规则。"""
        discussion = replace(initial_game(seed=7), phase=Phase.DAY_DISCUSSION)
        discussion_view = observation_for(discussion, alive_ids(discussion)[0])
        self.assertEqual(expected_discussion_order(discussion), discussion_view.public["discussion_order"])
        discussion_system, _ = model_prompts(discussion_view)
        self.assertIn("发言顺序", discussion_system)

        vote = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        vote_system, _ = model_prompts(observation_for(vote, alive_ids(vote)[0]))
        self.assertIn("投票期间看不到其他玩家的投票", vote_system)
        self.assertIn("所有投票完成后才公开票型", vote_system)

    def test_llm_policy_rejects_witch_save_without_attack_target(self):
        """模型在无袭击目标时请求救药，Policy 必须安全降级。"""
        state = initial_game(seed=7)
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        for wolf in wolves:
            state = submit_action(state, Action(wolf, "noop"))
        state = advance_phase(state)
        seer = player_id(state, Role.SEER)
        state = submit_action(state, Action(seer, "noop"))
        state = advance_phase(state)
        witch = player_id(state, Role.WITCH)
        adapter = ScriptedModelAdapter([
            '{"action_type":"witch_save","target_id":null}',
            '{"action_type":"witch_save","target_id":null}',
        ])

        action = LLMPolicy(witch, adapter).decide(observation_for(state, witch))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

    def test_llm_policy_rejects_wolf_kill_of_dead_target_before_rules(self):
        """狼人选择已死亡目标时，Policy 应先降级而不是制造规则拒绝。"""
        state = replace(initial_game(seed=7), phase=Phase.NIGHT_WOLF_CONFIRM)
        target = player_id(state, Role.VILLAGER)
        state = replace(
            state,
            players=tuple(replace(player, alive=False) if player.player_id == target else player for player in state.players),
        )
        wolf = next(player.player_id for player in state.players if player.role == Role.WOLF)
        records = []
        adapter = ScriptedModelAdapter([
            json.dumps({"action_type": "wolf_vote", "target_id": target}),
            json.dumps({"action_type": "wolf_vote", "target_id": target}),
        ])

        action = LLMPolicy(wolf, adapter, on_request=records.append).decide(observation_for(state, wolf))
        result = submit_action(state, action)

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)
        self.assertEqual("wolf_vote_target_not_alive", records[0]["schema_error_code"])
        self.assertNotIn("action_rejected", [event.event_type for event in result.events])

    def test_llm_policy_rejects_seer_inspection_of_dead_or_self_target_before_rules(self):
        """预言家不能把死亡玩家或自己作为查验目标提交给规则层。"""
        state = replace(initial_game(seed=7), phase=Phase.NIGHT_SEER)
        seer = player_id(state, Role.SEER)
        dead_target = next(player.player_id for player in state.players if player.player_id != seer)
        state = replace(
            state,
            players=tuple(replace(player, alive=False) if player.player_id == dead_target else player for player in state.players),
        )
        adapter = ScriptedModelAdapter([
            json.dumps({"action_type": "inspect", "target_id": dead_target}),
            json.dumps({"action_type": "inspect", "target_id": dead_target}),
        ])

        action = LLMPolicy(seer, adapter).decide(observation_for(state, seer))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

    def test_llm_policy_rejects_witch_poison_of_dead_or_self_target_before_rules(self):
        """女巫毒药目标必须是其他存活玩家。"""
        state = replace(initial_game(seed=7), phase=Phase.NIGHT_WITCH, night_victim=None)
        witch = player_id(state, Role.WITCH)
        dead_target = next(player.player_id for player in state.players if player.player_id != witch)
        state = replace(
            state,
            players=tuple(replace(player, alive=False) if player.player_id == dead_target else player for player in state.players),
        )
        adapter = ScriptedModelAdapter([
            json.dumps({"action_type": "witch_poison", "target_id": dead_target}),
            json.dumps({"action_type": "witch_poison", "target_id": dead_target}),
        ])

        action = LLMPolicy(witch, adapter).decide(observation_for(state, witch))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

    def test_llm_policy_rejects_witch_save_for_different_target_before_rules(self):
        """女巫解药只能指向当晚真实袭击目标。"""
        state = replace(initial_game(seed=7), phase=Phase.NIGHT_WITCH)
        witch = player_id(state, Role.WITCH)
        victim = next(player.player_id for player in state.players if player.player_id != witch)
        wrong_target = next(player.player_id for player in state.players if player.player_id not in {witch, victim})
        state = replace(state, night_victim=victim)
        adapter = ScriptedModelAdapter([
            json.dumps({"action_type": "witch_save", "target_id": wrong_target}),
            json.dumps({"action_type": "witch_save", "target_id": wrong_target}),
        ])

        action = LLMPolicy(witch, adapter).decide(observation_for(state, witch))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

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
        adapter = ScriptedModelAdapter(["这不是 JSON", "第二次仍不是 JSON"])
        action = LLMPolicy(player, adapter).decide(observation_for(state, player))
        self.assertEqual("noop", action.action_type)
        self.assertEqual(player, action.actor_id)
        self.assertEqual(2, action.model_calls)
        self.assertEqual("invalid_json", action.fallback_reason)

    def test_llm_policy_repairs_invalid_json_once_and_merges_metrics(self):
        """首次非 JSON 输出应触发一次短修复请求，成功后保留两次调用指标。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_DISCUSSION)
        player = player_id(state, Role.WOLF)
        records = []
        adapter = ScriptedModelAdapter([
            "这不是 JSON",
            '{"action_type":"speak","speech":"我会继续观察。"}',
        ])

        action = LLMPolicy(player, adapter, on_request=records.append).decide(observation_for(state, player))

        self.assertEqual("speak", action.action_type)
        self.assertEqual(2, action.model_calls)
        self.assertEqual(2, len(adapter.calls))
        self.assertIn("只返回一个 JSON 对象", adapter.calls[1][1])
        self.assertEqual(1, len(records))
        self.assertTrue(records[0]["repair_attempted"])
        self.assertTrue(records[0]["repair_succeeded"])
        self.assertEqual("invalid_json", records[0]["repair_reason"])
        self.assertEqual("invalid_json", records[0]["schema_error_code"])
        self.assertIsNone(records[0]["repair_schema_error_code"])

    def test_llm_policy_repairs_schema_failure_once(self):
        """Schema 失败也只能触发一次修复请求，避免无限重试。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_DISCUSSION)
        player = player_id(state, Role.WOLF)
        adapter = ScriptedModelAdapter([
            '{"action_type":"speak","extra":true}',
            '{"action_type":"speak","speech":"修复后的发言。"}',
        ])

        action = LLMPolicy(player, adapter).decide(observation_for(state, player))

        self.assertEqual("speak", action.action_type)
        self.assertEqual(2, action.model_calls)
        self.assertEqual(2, len(adapter.calls))

    def test_llm_policy_degrades_after_repair_attempt_fails(self):
        """修复请求仍失败时必须安全降级，且不能继续第三次请求。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_DISCUSSION)
        player = player_id(state, Role.WOLF)
        records = []
        adapter = ScriptedModelAdapter(["第一次不是 JSON", "第二次仍不是 JSON"])

        action = LLMPolicy(player, adapter, on_request=records.append).decide(observation_for(state, player))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("invalid_json", action.fallback_reason)
        self.assertEqual(2, action.model_calls)
        self.assertEqual(2, len(adapter.calls))
        self.assertFalse(records[0]["repair_succeeded"])

    def test_model_prompt_declares_phase_specific_action_protocol(self):
        """Prompt 必须给出当前阶段允许的行动枚举，减少模型协议漂移。"""
        state = initial_game(seed=7)
        wolf = player_id(state, Role.WOLF)
        system_prompt, _ = model_prompts(observation_for(state, wolf))
        self.assertIn("wolf_speak", system_prompt)
        self.assertIn("action_type", system_prompt)
        self.assertIn("noop", system_prompt)

    def test_day_vote_prompt_requires_target_or_explicit_abstention(self):
        """投票 Prompt 必须把 vote 和 abstain 的 target 约束说清楚。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        actor = alive_ids(state)[0]
        system_prompt, _ = model_prompts(observation_for(state, actor))

        self.assertIn("vote 必须提供存活且不是自己的 target_id", system_prompt)
        self.assertIn("abstain 或 noop 的 target_id 必须为 null", system_prompt)

    def test_model_prompt_compacts_authorized_events_without_changing_facts(self):
        """Prompt 压缩只移除审计元数据，保留授权事件的业务事实和完整 payload。"""
        state = initial_game(seed=7)
        wolf = player_id(state, Role.WOLF)
        public_event = Event(
            event_id="r1-night_wolf-e1-speech",
            round_number=1,
            phase=Phase.DAY_DISCUSSION,
            event_type="speech",
            payload={"speaker": "alice", "text": "我怀疑 bob。"},
            public=True,
            rule="public_discussion",
        )
        private_event = Event(
            event_id="r1-night_wolf-e2-inspection_result",
            round_number=1,
            phase=Phase.NIGHT_SEER,
            event_type="inspection_result",
            payload={"target": "bob", "is_wolf": True},
            public=False,
            recipients=(wolf,),
            rule="private_inspection_result",
        )
        state = replace(state, events=(public_event, private_event))

        _, user_prompt = model_prompts(observation_for(state, wolf))
        prompt = json.loads(user_prompt)

        self.assertIsInstance(prompt["untrusted_public_transcript"], list)
        self.assertEqual(
            {
                "round": 1,
                "phase": "day_discussion",
                "type": "speech",
                "data": {"speaker": "alice", "text": "我怀疑 bob。"},
            },
            prompt["untrusted_public_transcript"][0],
        )
        self.assertEqual(
            {
                "round": 1,
                "phase": "night_seer",
                "type": "inspection_result",
                "data": {"target": "bob", "is_wolf": True},
            },
            prompt["private_state"]["private_events"][0],
        )
        event_keys = set(prompt["untrusted_public_transcript"][0])
        event_keys.update(prompt["private_state"]["private_events"][0])
        for audit_field in ("event_id", "public", "recipients", "rule"):
            self.assertNotIn(audit_field, event_keys)

    def test_model_prompt_keeps_real_private_memory_and_omits_boilerplate(self):
        """Prompt 只删除固定无信息文案，真实私有记忆仍完整保留。"""
        state = initial_game(seed=7)
        wolf = player_id(state, Role.WOLF)
        players = tuple(
            replace(
                player,
                private_memory=("身份信息仅自己可见。", "alice 曾在投票中弃票。"),
            )
            if player.player_id == wolf
            else player
            for player in state.players
        )
        state = replace(state, players=players)

        _, user_prompt = model_prompts(observation_for(state, wolf))
        prompt = json.loads(user_prompt)

        self.assertEqual(["alice 曾在投票中弃票。"], prompt["private_state"]["private_memory"])

    def test_llm_policy_normalizes_common_action_aliases(self):
        """常见自然语言行动名应在 Policy 边界归一化为规则枚举。"""
        state = replace(initial_game(seed=7), phase=Phase.NIGHT_WOLF_CONFIRM)
        wolf = player_id(state, Role.WOLF)
        adapter = ScriptedModelAdapter(['{"action_type":"confirm_kill","target_id":"alice"}'])
        action = LLMPolicy(wolf, adapter).decide(observation_for(state, wolf))
        self.assertEqual("wolf_vote", action.action_type)

    def test_llm_policy_treats_non_string_decision_label_as_empty_metadata(self):
        """非关键 decision_label 缺失、为空或类型异常时不应否决合法行动。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_DISCUSSION)
        wolf = player_id(state, Role.WOLF)
        responses = [
            '{"action_type":"speak","speech":"继续观察。"}',
            '{"action_type":"speak","speech":"继续观察。","decision_label":null}',
            '{"action_type":"speak","speech":"继续观察。","decision_label":123}',
            '{"action_type":"speak","speech":"继续观察。","decision_label":true}',
        ]

        for response in responses:
            with self.subTest(response=response):
                action = LLMPolicy(wolf, ScriptedModelAdapter([response])).decide(
                    observation_for(state, wolf)
                )
                self.assertEqual("speak", action.action_type)
                self.assertEqual("", action.decision_label)
                self.assertEqual("", action.fallback_reason)
                self.assertEqual(1, action.model_calls)

    def test_llm_policy_rejects_unknown_fields_and_phase_actions(self):
        """Schema 或阶段协议不满足时必须降级，不能把错误行动交给规则层。"""
        state = initial_game(seed=7)
        wolf = player_id(state, Role.WOLF)
        unknown_field = ScriptedModelAdapter([
            '{"action_type":"wolf_kill","extra":true}',
            '{"action_type":"wolf_kill","extra":true}',
        ])
        action = LLMPolicy(wolf, unknown_field).decide(observation_for(state, wolf))
        self.assertEqual("noop", action.action_type)
        self.assertEqual("invalid_model_output", action.decision_label)

        wrong_phase = ScriptedModelAdapter(['{"action_type":"speak"}', '{"action_type":"speak"}'])
        action = LLMPolicy(wolf, wrong_phase).decide(observation_for(state, wolf))
        self.assertEqual("noop", action.action_type)
        self.assertEqual("invalid_model_output", action.decision_label)

    def test_llm_policy_emits_redacted_request_trace_with_agent_and_action(self):
        """请求追踪应关联 Agent 和阶段，但不能保存 Prompt 或原始响应。"""
        state = replace(initial_game(seed=7), phase=Phase.NIGHT_WOLF_CONFIRM)
        wolf = player_id(state, Role.WOLF)
        records = []
        adapter = ScriptedModelAdapter(['{"action_type":"confirm_kill","target_id":"alice"}'])
        action = LLMPolicy(wolf, adapter, on_request=records.append).decide(observation_for(state, wolf))

        self.assertEqual("wolf_vote", action.action_type)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual(wolf, record["agent_id"])
        self.assertEqual("night_wolf_confirm", record["phase"])
        self.assertEqual("succeeded", record["request_status"])
        self.assertEqual("parsed", record["decision_status"])
        self.assertEqual("wolf_vote", record["parsed_action_type"])
        self.assertEqual(64, len(record["prompt_sha256"]))
        self.assertEqual(64, len(record["response_sha256"]))
        self.assertNotIn("system_prompt", record)
        self.assertNotIn("user_prompt", record)
        self.assertNotIn("response_text", record)

    def test_llm_policy_trace_distinguishes_schema_fallback(self):
        """Schema 失败必须在请求追踪中与传输失败区分。"""
        state = initial_game(seed=7)
        wolf = player_id(state, Role.WOLF)
        records = []
        adapter = ScriptedModelAdapter([
            '{"action_type":"wolf_kill","extra":true}',
            '{"action_type":"wolf_kill","extra":true}',
        ])
        action = LLMPolicy(wolf, adapter, on_request=records.append).decide(observation_for(state, wolf))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)
        self.assertEqual("degraded", records[0]["decision_status"])
        self.assertEqual("schema_validation", records[0]["fallback_reason"])
        self.assertEqual("unknown_field", records[0]["schema_error_code"])
        self.assertEqual("unknown_field", records[0]["repair_schema_error_code"])
        self.assertEqual("succeeded", records[0]["request_status"])

    def test_llm_policy_trace_classifies_invalid_vote_target_without_raw_error(self):
        """投票目标错误只记录稳定分类码，不记录异常原文。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        actor, dead = alive_ids(state)[:2]
        players = tuple(
            replace(player, alive=False) if player.player_id == dead else player
            for player in state.players
        )
        state = replace(state, players=players)
        records = []
        invalid_vote = json.dumps({"action_type": "vote", "target_id": dead})
        adapter = ScriptedModelAdapter([invalid_vote, invalid_vote])

        action = LLMPolicy(actor, adapter, on_request=records.append).decide(observation_for(state, actor))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("vote_target_not_alive", records[0]["schema_error_code"])
        self.assertNotIn("必须指向存活玩家", json.dumps(records[0], ensure_ascii=False))

    def test_llm_metrics_distinguish_fallback_noop_abstain_and_effective_action(self):
        """游戏指标应区分请求数、降级 noop、弃票和有效行动。"""
        state = initial_game(seed=7)
        wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
        state = submit_action(
            state,
            Action(
                wolves[0],
                "noop",
                model_calls=1,
                decision_label="invalid_model_output",
                fallback_reason="schema_validation",
            ),
        )
        state = submit_action(state, Action(wolves[1], "wolf_kill", "alice", model_calls=1))

        self.assertEqual(2, state.metrics["request_count"])
        self.assertEqual(1, state.metrics["fallback_count"])
        self.assertEqual(1, state.metrics["noop_count"])
        self.assertEqual(1, state.metrics["schema_failure_count"])
        self.assertEqual(1, state.metrics["effective_action_count"])

    def test_request_trace_store_appends_jsonl_and_artifact_store_reports_it(self):
        """请求追踪应独立落盘为 JSONL，并出现在工件清单中。"""
        state = initial_game(seed=7)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace_store = RequestTraceStore(root / "llm_requests.jsonl")
            trace_store.append({"request_id": "req-1", "agent_id": "alice", "phase": "night_wolf"})
            trace_store.append({"request_id": "req-2", "agent_id": "bob", "phase": "night_wolf"})
            artifacts = ArtifactStore(root).write(state, evaluate_game(state, offline=False))
            lines = (root / "llm_requests.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertIn("llm_requests", artifacts)
        self.assertEqual(2, len(lines))
        self.assertEqual("req-1", json.loads(lines[0])["request_id"])

    def test_artifact_store_writes_spectator_html(self):
        """每局工件目录必须包含公开观战页面。"""
        state = GameEngine(seed=7).run(max_rounds=1)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = ArtifactStore(Path(directory)).write(state, evaluate_game(state))
            spectator_path = Path(artifacts["spectator"])

            self.assertTrue(spectator_path.exists())
            self.assertIn("WEREWOLF ARENA", spectator_path.read_text(encoding="utf-8"))

    def test_artifact_store_only_writes_god_view_when_enabled(self):
        """上帝视角页面必须由显式开关控制。"""
        state = GameEngine(seed=7).run(max_rounds=1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            normal = ArtifactStore(root / "normal").write(state, evaluate_game(state))
            god = ArtifactStore(root / "god").write(state, evaluate_game(state), god_view=True)

            self.assertNotIn("god_view", normal)
            self.assertNotIn("god_view.html", {path.name for path in (root / "normal").iterdir()})
            self.assertTrue(Path(god["god_view"]).exists())

    def test_cli_god_view_flag_reports_god_view_artifact(self):
        """CLI 开启上帝视角后必须在 JSON 工件清单中报告页面。"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--seed",
                    "7",
                    "--max-rounds",
                    "1",
                    "--json",
                    "--god-view",
                    "--output-dir",
                    directory,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertTrue(Path(payload["artifacts"]["god_view"]).exists())

    def test_god_view_is_separate_from_public_spectator(self):
        """普通观众页与完整审计页必须保持数据隔离。"""
        with tempfile.TemporaryDirectory() as directory:
            normal_dir = Path(directory) / "normal"
            god_dir = Path(directory) / "god"
            subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--seed",
                    "7",
                    "--max-rounds",
                    "1",
                    "--output-dir",
                    str(normal_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--seed",
                    "7",
                    "--max-rounds",
                    "1",
                    "--god-view",
                    "--output-dir",
                    str(god_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            public_html = (normal_dir / "spectator.html").read_text(encoding="utf-8")
            god_html = (god_dir / "god_view.html").read_text(encoding="utf-8")

        self.assertNotIn("wolf_negotiation_message", public_html)
        self.assertIn("wolf_negotiation_message", god_html)
        self.assertIn("wolf", god_html)
        self.assertIn('data-event-id="', god_html)

    def test_spectate_mode_prints_only_public_narrative(self):
        """终端观战输出公开叙事，不暴露私密事件类型。"""
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT / "main.py"),
                "--demo",
                "--seed",
                "7",
                "--max-rounds",
                "1",
                "--spectate",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("天亮", result.stdout)
        self.assertNotIn("wolf_negotiation_message", result.stdout)
        self.assertNotIn("Role.WOLF", result.stdout)

    def test_json_spectate_keeps_stdout_parseable_and_reports_spectator_artifact(self):
        """JSON 观战模式把叙事放到 stderr，stdout 仍必须是完整合法 JSON。"""
        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT / "main.py"),
                "--demo",
                "--seed",
                "7",
                "--max-rounds",
                "1",
                "--json",
                "--spectate",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(result.stdout)
        self.assertIn("spectator", payload["artifacts"])
        self.assertIn("天亮", result.stderr)
        self.assertNotIn("wolf_negotiation_message", result.stderr)

    def test_spectator_timeline_uses_source_event_round_and_phase(self):
        """过滤私有事件后，时间线仍使用公开事件自身的轮次和阶段。"""
        state = replace(initial_game(seed=7), events=(
            Event(
                "private", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message",
                {"text": "secret"}, public=False, recipients=("bob",),
            ),
            Event(
                "public", 2, Phase.DAY_DISCUSSION, "speech",
                {"speaker": "alice", "text": "公开发言"},
            ),
        ))

        html = render_spectator_html(state)

        self.assertIn('<span class="round">R2</span>', html)
        self.assertIn("白天讨论", html)
        self.assertNotIn("R1</span>", html)

    def test_llm_engine_persists_one_trace_per_model_decision(self):
        """真实 Policy 调度时，每个存活 Agent 的逻辑请求都应进入同一 JSONL。"""
        state = initial_game(seed=7)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace_store = RequestTraceStore(root / "llm_requests.jsonl")
            adapter = ScriptedModelAdapter([])
            policies = {
                player.player_id: LLMPolicy(player.player_id, adapter, on_request=trace_store.append)
                for player in state.players
            }
            result = GameEngine(seed=7, policies=policies).run(max_rounds=1)
            records = [json.loads(line) for line in (root / "llm_requests.jsonl").read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result.metrics["request_count"], len(records))
        self.assertEqual(18, len(records))
        self.assertEqual({"alice", "bob", "carol", "david", "eve", "frank"}, {record["agent_id"] for record in records})

    def test_noop_is_a_safe_no_action_in_every_phase(self):
        """模型失败后的 noop 应可被环境结算，而不是制造规则拒绝。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        actor = alive_ids(state)[0]
        accepted = submit_action(state, Action(actor, "noop", decision_label="llm_timeout"))
        self.assertEqual("noop", accepted.pending_actions[0].action_type)
        self.assertNotIn("action_rejected", [event.event_type for event in accepted.events])

    def test_model_adapter_calculates_cost_and_limits_output_tokens(self):
        """适配器应按配置价格计算费用，并将输出上限传给兼容网关。"""
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            input_price_per_million=1.0,
            output_price_per_million=2.0,
            max_output_tokens=128,
        )
        response = FakeHTTPResponse(
            {"choices": [{"message": {"content": '{"action_type":"noop"}'}}], "usage": {"prompt_tokens": 1000, "completion_tokens": 500}}
        )
        with patch("werewolf_arena.policies.request.urlopen", return_value=response) as urlopen:
            result = adapter.complete("system", "user")
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(128, payload["max_tokens"])
        self.assertAlmostEqual(0.002, result.cost_usd)

    def test_model_adapter_escalates_budget_after_truncated_json(self):
        """模型以 finish_reason=length 截断时，应升档预算重试而不是直接降级。"""
        truncated = FakeHTTPResponse(
            {
                "choices": [{"finish_reason": "length", "message": {"content": '{"action_type":"'}}],
                "usage": {"completion_tokens": 64},
            }
        )
        complete = FakeHTTPResponse(
            {
                "choices": [{"finish_reason": "stop", "message": {"content": '{"action_type":"noop"}'}}],
                "usage": {"completion_tokens": 8},
            }
        )
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            max_output_tokens=64,
            max_output_tokens_limit=128,
            max_output_retries=1,
        )
        with patch("werewolf_arena.policies.request.urlopen", side_effect=[truncated, complete]) as urlopen:
            result = adapter.complete("system", "user")

        payloads = [json.loads(call.args[0].data.decode("utf-8")) for call in urlopen.call_args_list]
        self.assertEqual([64, 128], [payload["max_tokens"] for payload in payloads])
        self.assertEqual('{"action_type":"noop"}', result.text)
        self.assertFalse(result.truncated)
        self.assertEqual("stop", result.finish_reason)
        self.assertEqual(128, result.requested_max_tokens)
        self.assertEqual(1, result.output_retry_count)

    def test_model_adapter_stops_at_output_budget_limit_after_repeated_truncation(self):
        """连续截断时应停在硬上限并返回可观测的 output_truncated。"""
        truncated = FakeHTTPResponse(
            {
                "choices": [{"finish_reason": "length", "message": {"content": "{"}}],
                "usage": {"completion_tokens": 64},
            }
        )
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            max_output_tokens=64,
            max_output_tokens_limit=128,
            max_output_retries=3,
        )
        with patch("werewolf_arena.policies.request.urlopen", side_effect=[truncated, truncated]) as urlopen:
            result = adapter.complete("system", "user")

        self.assertEqual(2, urlopen.call_count)
        self.assertTrue(result.truncated)
        self.assertEqual("output_truncated", result.failure_reason)
        self.assertEqual("length", result.finish_reason)
        self.assertEqual(128, result.requested_max_tokens)
        self.assertEqual(1, result.output_retry_count)

    def test_llm_trace_records_output_truncation_metadata(self):
        """请求追踪必须区分输出截断和普通模型失败。"""
        state = initial_game(seed=7)
        actor = player_id(state, Role.SEER)
        records = []

        class TruncatedAdapter:
            def complete(self, system_prompt, user_prompt):
                return ModelResponse(
                    text='{"action_type":"',
                    output_tokens=64,
                    failure_reason="output_truncated",
                    finish_reason="length",
                    truncated=True,
                    requested_max_tokens=64,
                )

        action = LLMPolicy(actor, TruncatedAdapter(), on_request=records.append).decide(
            observation_for(state, actor)
        )

        self.assertEqual("noop", action.action_type)
        self.assertEqual(1, len(records))
        self.assertEqual("output_truncated", records[0]["failure_reason"])
        self.assertEqual("length", records[0]["finish_reason"])
        self.assertTrue(records[0]["truncated"])
        self.assertEqual(64, records[0]["requested_max_tokens"])

    def test_model_adapter_controls_thinking_mode_for_structured_actions(self):
        """结构化行动默认关闭 thinking，也允许 auto 模式省略供应商专属字段。"""
        response = FakeHTTPResponse(
            {"choices": [{"message": {"content": '{"action_type":"noop"}'}}], "usage": {}}
        )
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
        )
        with patch("werewolf_arena.policies.request.urlopen", return_value=response) as urlopen:
            adapter.complete("system", "user")
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual({"type": "disabled"}, payload["thinking"])

        auto_adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            thinking="auto",
        )
        with patch("werewolf_arena.policies.request.urlopen", return_value=response) as urlopen:
            auto_adapter.complete("system", "user")
        auto_payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertNotIn("thinking", auto_payload)

    def test_environment_defaults_to_fast_structured_action_configuration(self):
        """环境默认值应优先保证结构化行动完整返回和低延迟。"""
        with patch.dict(
            os.environ,
            {
                "WEREWOLF_LLM_ENDPOINT": "https://example.invalid/v1/chat/completions",
                "WEREWOLF_LLM_API_KEY": "test-secret",
                "WEREWOLF_LLM_MODEL": "test-model",
            },
            clear=True,
        ):
            adapter = OpenAICompatibleModelAdapter.from_environment()

        self.assertEqual(2048, adapter.max_output_tokens)
        self.assertEqual(4096, adapter.max_output_tokens_limit)
        self.assertEqual(1, adapter.max_output_retries)
        self.assertEqual("disabled", adapter.thinking)

    def test_llm_adapter_loads_project_dotenv_before_reading_configuration(self):
        """狼人杀真实模型入口应自动加载项目 .env，而不是要求手动 export。"""
        with patch.dict(
            os.environ,
            {
                "WEREWOLF_LLM_ENDPOINT": "https://example.invalid/v1/chat/completions",
                "WEREWOLF_LLM_API_KEY": "test-secret",
                "WEREWOLF_LLM_MODEL": "test-model",
            },
            clear=True,
        ), patch("werewolf_arena.policies.load_dotenv") as load_dotenv:
            OpenAICompatibleModelAdapter.from_environment()

        self.assertIn(PROJECT.parents[1] / ".env", {call.args[0] for call in load_dotenv.call_args_list})

    def test_llm_policy_rejects_vote_without_target_before_rules(self):
        """vote 没有目标时应在 Policy 层降级，不进入规则层制造拒绝事件。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        actor = alive_ids(state)[0]
        adapter = ScriptedModelAdapter(['{"action_type":"vote"}', '{"action_type":"vote"}'])

        action = LLMPolicy(actor, adapter).decide(observation_for(state, actor))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

    def test_llm_policy_rejects_vote_for_dead_target_before_rules(self):
        """vote 指向已死亡玩家时应在 Policy 层降级，不提交非法 Action。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        actor, dead = alive_ids(state)[:2]
        players = tuple(
            replace(player, alive=False) if player.player_id == dead else player
            for player in state.players
        )
        state = replace(state, players=players)
        invalid_vote = json.dumps({"action_type": "vote", "target_id": dead})
        adapter = ScriptedModelAdapter([invalid_vote, invalid_vote])

        action = LLMPolicy(actor, adapter).decide(observation_for(state, actor))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

    def test_llm_policy_rejects_abstain_with_target_before_rules(self):
        """abstain 不允许携带目标，避免模型把弃票和投票混用。"""
        state = replace(initial_game(seed=7), phase=Phase.DAY_VOTE)
        actor, target = alive_ids(state)[:2]
        invalid_abstain = json.dumps({"action_type": "abstain", "target_id": target})
        adapter = ScriptedModelAdapter([invalid_abstain, invalid_abstain])

        action = LLMPolicy(actor, adapter).decide(observation_for(state, actor))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("schema_validation", action.fallback_reason)

    def test_evaluation_reports_real_llm_mode(self):
        """评测报告的 offline 标记必须由调用方传入，而不是写死。"""
        state = GameEngine(seed=7).run(max_rounds=1)
        self.assertFalse(evaluate_game(state, offline=False)["offline"])

    def test_live_model_adapter_requires_endpoint_and_secret(self):
        """真实模型缺少 endpoint、密钥或模型名时应明确拒绝启动。"""
        with self.assertRaises(LLMConfigurationError):
            OpenAICompatibleModelAdapter(endpoint="", api_key="", model="")

    def test_model_adapter_retries_timeout_and_returns_latency_metrics(self):
        events = []
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            timeout_seconds=1,
            max_retries=1,
            retry_backoff_seconds=0,
            on_event=events.append,
        )
        response = FakeHTTPResponse(
            {"choices": [{"message": {"content": '{"action_type":"noop"}'}}], "usage": {"prompt_tokens": 3, "completion_tokens": 4}}
        )

        with patch("werewolf_arena.policies.request.urlopen", side_effect=[TimeoutError(), response]) as urlopen:
            result = adapter.complete("system", "user")

        self.assertEqual(2, urlopen.call_count)
        self.assertEqual('{"action_type":"noop"}', result.text)
        self.assertEqual(2, result.attempts)
        self.assertEqual(1, result.retry_count)
        self.assertEqual("", result.failure_reason)
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertTrue(any(event["event"] == "request_retrying" for event in events))

    def test_model_adapter_degrades_after_timeout_instead_of_raising(self):
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            timeout_seconds=1,
            max_retries=1,
            retry_backoff_seconds=0,
        )

        with patch("werewolf_arena.policies.request.urlopen", side_effect=[TimeoutError(), TimeoutError()]):
            result = adapter.complete("system", "user")

        self.assertEqual("", result.text)
        self.assertEqual("timeout", result.failure_reason)
        self.assertEqual(2, result.attempts)
        self.assertEqual(1, result.retry_count)

    def test_non_retryable_auth_error_returns_safe_failure_once(self):
        adapter = OpenAICompatibleModelAdapter(
            endpoint="https://example.invalid/v1/chat/completions",
            api_key="test-secret",
            model="test-model",
            max_retries=3,
            retry_backoff_seconds=0,
        )
        error = HTTPError(adapter.endpoint, 401, "unauthorized", {}, None)

        with patch("werewolf_arena.policies.request.urlopen", side_effect=error) as urlopen:
            result = adapter.complete("system", "user")

        self.assertEqual(1, urlopen.call_count)
        self.assertEqual("http_401", result.failure_reason)
        self.assertNotIn("test-secret", result.text)

    def test_environment_controls_timeout_and_retry_policy_without_exposing_key(self):
        with patch.dict(
            os.environ,
            {
                "WEREWOLF_LLM_ENDPOINT": "https://example.invalid/v1/chat/completions",
                "WEREWOLF_LLM_API_KEY": "test-secret",
                "WEREWOLF_LLM_MODEL": "test-model",
                "WEREWOLF_LLM_TIMEOUT_SECONDS": "9",
                "WEREWOLF_LLM_MAX_RETRIES": "2",
                "WEREWOLF_LLM_RETRY_BACKOFF_SECONDS": "0.25",
                "WEREWOLF_LLM_MAX_OUTPUT_TOKENS": "256",
                "WEREWOLF_LLM_INPUT_PRICE_PER_MILLION": "1.5",
                "WEREWOLF_LLM_OUTPUT_PRICE_PER_MILLION": "3",
            },
            clear=False,
        ):
            adapter = OpenAICompatibleModelAdapter.from_environment()

        self.assertEqual(9, adapter.timeout_seconds)
        self.assertEqual(2, adapter.max_retries)
        self.assertEqual(0.25, adapter.retry_backoff_seconds)
        self.assertEqual(256, adapter.max_output_tokens)
        self.assertEqual(1.5, adapter.input_price_per_million)
        self.assertEqual(3, adapter.output_price_per_million)

    def test_llm_policy_turns_adapter_failure_into_noop_with_failure_metrics(self):
        state = initial_game(seed=7)
        player = player_id(state, Role.WOLF)

        class FailedAdapter:
            def complete(self, system_prompt, user_prompt):
                return ModelResponse(
                    text="",
                    attempts=2,
                    retry_count=1,
                    failure_reason="timeout",
                    latency_ms=30000,
                )

        action = LLMPolicy(player, FailedAdapter()).decide(observation_for(state, player))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("llm_timeout", action.decision_label)
        self.assertEqual(2, action.model_calls)
        self.assertEqual(30000, action.latency_ms)

    def test_llm_policy_catches_unexpected_adapter_exception_without_secret_text(self):
        state = initial_game(seed=7)
        player = player_id(state, Role.WOLF)

        class BrokenAdapter:
            def complete(self, system_prompt, user_prompt):
                raise RuntimeError("provider internals contain a secret")

        action = LLMPolicy(player, BrokenAdapter()).decide(observation_for(state, player))

        self.assertEqual("noop", action.action_type)
        self.assertEqual("llm_adapter_error", action.decision_label)
        self.assertNotIn("secret", action.decision_label)

    def test_game_continues_when_model_adapter_times_out(self):
        state = initial_game(seed=7)
        policies = {
            player.player_id: LLMPolicy(
                player.player_id,
                type("FailedAdapter", (), {
                    "complete": lambda self, system_prompt, user_prompt: ModelResponse(
                        text="", attempts=1, failure_reason="timeout", latency_ms=30000
                    )
                })(),
            )
            for player in state.players
        }

        result = GameEngine(seed=7, policies=policies).run(max_rounds=1)

        self.assertEqual("DRAW", result.status)
        self.assertGreater(result.metrics["model_calls"], 0)
        self.assertGreater(result.metrics["latency_ms"], 0)
        self.assertEqual(result.metrics["model_calls"], result.metrics["model_failures"])

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

    def test_checkpoint_resume_from_wolf_confirmation_matches_continuous_game(self):
        """在狼人确认阶段后中断恢复，结果必须与连续运行一致。"""
        continuous = GameEngine(seed=7).run(max_rounds=2)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            interrupted = GameEngine(seed=7).run(
                max_rounds=2,
                interrupt_after_phase=Phase.NIGHT_WOLF_CONFIRM,
                checkpoint_path=checkpoint,
            )
            self.assertEqual("INTERRUPTED", interrupted.status)
            resumed = GameEngine.resume(checkpoint, max_rounds=2)
        self.assertEqual(continuous.to_dict(), resumed.to_dict())

    def test_public_narrative_ignores_private_events_and_renders_speech_and_votes(self):
        """叙事层只处理公开事件，并保留发言和票型事实。"""
        public_speech = Event(
            "e1", 1, Phase.DAY_DISCUSSION, "speech", {"speaker": "alice", "text": "我怀疑 bob。"}
        )
        public_vote = Event(
            "e2", 1, Phase.DAY_VOTE, "vote_revealed",
            {"ballots": {"alice": "bob"}, "counts": {"bob": 1}},
        )
        private_message = Event(
            "e3", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message", {"text": "攻击 bob"},
            public=False, recipients=("alice", "bob"),
        )

        rendered = render_public_events((public_speech, public_vote, private_message))
        joined = " ".join(rendered)

        self.assertIn("alice", joined)
        self.assertIn("bob", joined)
        self.assertNotIn("攻击 bob", joined)

    def test_spectator_html_escapes_public_speech_and_omits_private_data(self):
        """观战页面必须转义公开发言且不能包含私密事件或身份字段。"""
        state = replace(initial_game(seed=7), events=(
            Event(
                "e1", 1, Phase.DAY_DISCUSSION, "speech",
                {"speaker": "alice", "text": "<script>alert(1)</script>"},
            ),
            Event(
                "e2", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message", {"text": "secret"},
                public=False, recipients=("alice",),
            ),
        ))

        html = render_spectator_html(state)

        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("secret", html)
        self.assertNotIn('role="wolf"', html)

    def test_god_view_contains_private_audit_data_and_escapes_text(self):
        """上帝视角应展示完整审计信息，同时转义动态文本。"""
        state = replace(initial_game(seed=7), events=(
            Event(
                "private", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message",
                {"speaker": "bob", "text": "<script>secret</script>"},
                public=False, recipients=("bob", "eve"),
            ),
            Event(
                "inspect", 1, Phase.NIGHT_SEER, "inspection_result",
                {"target": "alice", "alignment": "good"},
                public=False, recipients=("frank",),
            ),
        ))

        html = render_god_view_html(state)

        self.assertIn("wolf_negotiation_message", html)
        self.assertIn("inspection_result", html)
        self.assertIn("wolf", html)
        self.assertIn("&lt;script&gt;secret&lt;/script&gt;", html)
        self.assertIn("recipients", html)
        self.assertNotIn("window.__GAME_STATE__", html)

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

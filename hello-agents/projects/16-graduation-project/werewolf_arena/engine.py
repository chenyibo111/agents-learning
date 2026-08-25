"""按游戏阶段调度 Policy、规则和 checkpoint 的运行时。"""

from dataclasses import replace
from pathlib import Path
from typing import Mapping

from .policies import Policy, RulePolicy
from .rules import advance_phase, finish_draw, initial_game, submit_action
from .schemas import GameState, Phase, Role
from .storage import CheckpointStore
from .visibility import observation_for


class GameEngine:
    """编排阶段、Policy、规则与 checkpoint 的单局运行时。"""

    def __init__(self, seed: int = 7, policies: Mapping[str, Policy] | None = None):
        """保存可重放 seed 与可选的按玩家覆盖策略；缺失时回退 RulePolicy。"""
        self.seed = seed
        self.policies = dict(policies or {})

    def _actors_for_phase(self, state: GameState) -> list[str]:
        """列出当前阶段必须行动的存活玩家，确保死人不会被调度。"""
        if state.phase == Phase.NIGHT_WOLF:
            return [player.player_id for player in state.players if player.alive and player.role == Role.WOLF]
        if state.phase == Phase.NIGHT_SEER:
            return [player.player_id for player in state.players if player.alive and player.role == Role.SEER]
        if state.phase == Phase.NIGHT_WITCH:
            return [player.player_id for player in state.players if player.alive and player.role == Role.WITCH]
        if state.phase in {Phase.DAY_DISCUSSION, Phase.DAY_VOTE}:
            return [player.player_id for player in state.players if player.alive]
        return []

    def _advance_one_phase(self, state: GameState) -> GameState:
        """依次收集本阶段行动，再由规则引擎一次性结算阶段结果。"""
        for player_id in self._actors_for_phase(state):
            # Observation 在每次行动前重新生成：白天后序玩家可看到前序公开发言/投票。
            policy = self.policies.get(player_id, RulePolicy(player_id))
            state = submit_action(state, policy.decide(observation_for(state, player_id)))
        return advance_phase(state)

    def run(
        self,
        max_rounds: int = 3,
        interrupt_after_phase: Phase | None = None,
        checkpoint_path: Path | None = None,
        initial_state: GameState | None = None,
    ) -> GameState:
        """从新局或已有 checkpoint 状态运行到胜负、平局或指定中断点。"""
        if max_rounds < 1:
            raise ValueError("max_rounds 至少为 1")
        state = initial_state or initial_game(self.seed)
        # 恢复时只重置运行标志；已保存的阶段、事件和 pending_actions 均保持原样。
        if state.status == "INTERRUPTED":
            state = replace(state, status="RUNNING")
        while state.status == "RUNNING":
            # 最大轮数是成本和死循环保护，不把未分胜负的局误判为任何阵营胜利。
            if state.round_number > max_rounds:
                state = finish_draw(state)
                break
            # 每次循环只推进一个阶段，便于 checkpoint、回放和定位失败。
            state = self._advance_one_phase(state)
            if checkpoint_path:
                CheckpointStore(Path(checkpoint_path)).save(state)
            if interrupt_after_phase is not None and state.phase == interrupt_after_phase and state.status == "RUNNING":
                # 用于模拟进程中断；恢复会从当前 phase 的下一次调度继续。
                state = replace(state, status="INTERRUPTED")
                if checkpoint_path:
                    CheckpointStore(Path(checkpoint_path)).save(state)
                return state
        if checkpoint_path:
            CheckpointStore(Path(checkpoint_path)).save(state)
        return state

    @classmethod
    def resume(cls, checkpoint_path: Path, max_rounds: int = 3, policies: Mapping[str, Policy] | None = None) -> GameState:
        """读取版本化 checkpoint，并使用原 seed 和可选新策略继续该局。"""
        state = CheckpointStore(Path(checkpoint_path)).load()
        return cls(seed=state.seed, policies=policies).run(
            max_rounds=max_rounds,
            checkpoint_path=Path(checkpoint_path),
            initial_state=state,
        )

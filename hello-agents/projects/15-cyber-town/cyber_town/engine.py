"""事件驱动 tick 引擎。"""

from dataclasses import replace
from pathlib import Path
from typing import Mapping

from .policies import Policy, default_policies
from .schemas import Event, SimulationState
from .storage import CheckpointStore
from .visibility import observation_for
from .world import apply_action, initial_world


class SimulationEngine:
    def __init__(self, seed: int = 7, policies: Mapping[str, Policy] | None = None):
        self.seed = seed
        self.policies = dict(policies or default_policies())

    def _step(self, state: SimulationState) -> SimulationState:
        tick = state.world.tick
        world = state.world
        events = list(state.events)
        for agent in world.agents:
            policy = self.policies.get(agent.agent_id)
            if policy is None:
                raise KeyError(f"缺少 Agent Policy: {agent.agent_id}")
            observation = observation_for(world, agent.agent_id, events)
            action = policy.decide(observation)
            world, event = apply_action(world, action, tick, events)
            events.append(event)
        return replace(state, world=replace(world, tick=tick + 1), events=tuple(events), status="RUNNING")

    def run(
        self,
        ticks: int = 1,
        interrupt_after_tick: int | None = None,
        checkpoint_path: Path | None = None,
        initial_state: SimulationState | None = None,
    ) -> SimulationState:
        if ticks < 0:
            raise ValueError("ticks 不能为负数")
        state = initial_state or SimulationState(initial_world(self.seed), (), "RUNNING", self.seed)
        target_tick = state.world.tick + ticks
        while state.world.tick < target_tick:
            state = self._step(state)
            if checkpoint_path:
                CheckpointStore(Path(checkpoint_path)).save(state)
            if interrupt_after_tick is not None and state.world.tick >= interrupt_after_tick:
                state = replace(state, status="INTERRUPTED")
                if checkpoint_path:
                    CheckpointStore(Path(checkpoint_path)).save(state)
                return state
        state = replace(state, status="COMPLETED")
        if checkpoint_path:
            CheckpointStore(Path(checkpoint_path)).save(state)
        return state

    @classmethod
    def resume(
        cls,
        checkpoint_path: Path,
        ticks: int = 1,
        policies: Mapping[str, Policy] | None = None,
    ) -> SimulationState:
        state = CheckpointStore(Path(checkpoint_path)).load()
        return cls(seed=state.seed, policies=policies).run(
            ticks=ticks, checkpoint_path=Path(checkpoint_path), initial_state=state
        )


def replay_signature(state: SimulationState) -> tuple[dict, tuple[dict, ...]]:
    return state.world.to_dict(), tuple(event.to_dict() for event in state.events)

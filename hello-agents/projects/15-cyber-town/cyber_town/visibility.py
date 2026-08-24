"""把上帝视角世界投影为单个 Agent 被授权看到的 Observation。"""

from typing import Iterable

from .schemas import Event, Observation, WorldState


def observation_for(world: WorldState, agent_id: str, events: Iterable[Event]) -> Observation:
    agent = next((item for item in world.agents if item.agent_id == agent_id), None)
    if agent is None:
        raise KeyError(f"未知 Agent: {agent_id}")
    own_state = agent.to_dict()
    visible_events = tuple(event.to_dict() for event in events if event.public)
    return Observation(
        agent_id=agent_id,
        tick=world.tick,
        public_facts=dict(world.public_facts),
        market=dict(world.market),
        own_state=own_state,
        visible_events=visible_events,
    )

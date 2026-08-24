"""共享环境和不可绕过的行动规则。"""

from dataclasses import replace
import random
from typing import Iterable

from .schemas import Action, AgentState, Event, WorldState


def initial_world(seed: int = 7) -> WorldState:
    weather = random.Random(seed).choice(("晴", "多云"))
    return WorldState(
        tick=0,
        public_facts={
            "town": "赛博小镇",
            "weather": weather,
            "seed": seed,
            "initial_total_balance": 25,
            "initial_inventory": {"map": 1},
        },
        market={"offers": []},
        agents=(
            AgentState(
                "merchant", "商人", ("出售地图",), 10, {"map": 1}, ("merchant-secret",), {"researcher": 0}
            ),
            AgentState(
                "researcher", "研究员", ("购买地图",), 15, {}, ("researcher-secret",), {"merchant": 0}
            ),
            AgentState(
                "courier", "信使", ("传播消息",), 0, {}, ("courier-secret",), {"merchant": 0, "researcher": 0}
            ),
        ),
    )


def _event_id(tick: int, action: Action, events: Iterable[Event]) -> str:
    return f"t{tick}-e{sum(1 for _ in events)}-{action.agent_id}-{action.action_type}"


def _agent(world: WorldState, agent_id: str) -> AgentState | None:
    return next((agent for agent in world.agents if agent.agent_id == agent_id), None)


def _replace_agents(world: WorldState, agents: list[AgentState]) -> WorldState:
    return replace(world, agents=tuple(agents))


def _rejected(world: WorldState, action: Action, tick: int, rule: str, events: Iterable[Event]) -> tuple[WorldState, Event]:
    return world, Event(
        _event_id(tick, action, events), tick, "action_rejected", action.agent_id, action.target_id,
        {"action_type": action.action_type, "reason": rule}, True, rule
    )


def apply_action(
    world: WorldState,
    action: Action,
    tick: int,
    events: Iterable[Event] = (),
) -> tuple[WorldState, Event]:
    """执行一个行动；所有资源改变都必须经过这里。"""
    prior_events = tuple(events)
    actor = _agent(world, action.agent_id)
    target = _agent(world, action.target_id) if action.target_id else None
    if actor is None:
        return _rejected(world, action, tick, "unknown_actor", prior_events)

    if action.action_type == "offer":
        if target is None:
            return _rejected(world, action, tick, "unknown_target", prior_events)
        if not action.item or action.quantity <= 0:
            return _rejected(world, action, tick, "invalid_quantity", prior_events)
        if action.price < 0:
            return _rejected(world, action, tick, "invalid_price", prior_events)
        if actor.inventory.get(action.item, 0) < action.quantity:
            return _rejected(world, action, tick, "insufficient_inventory", prior_events)
        event = Event(
            _event_id(tick, action, prior_events), tick, "offer", action.agent_id, target.agent_id,
            {"item": action.item, "quantity": action.quantity, "price": action.price}, True, "offer_valid"
        )
        market = dict(world.market)
        offers = list(market.get("offers", []))
        offers.append({**event.payload, "offer_id": event.event_id, "seller_id": action.agent_id, "buyer_id": target.agent_id})
        market["offers"] = offers
        return replace(world, market=market), event

    if action.action_type == "accept":
        if target is None or not action.item or action.quantity <= 0:
            return _rejected(world, action, tick, "invalid_accept", prior_events)
        offer = next(
            (
                event for event in reversed(prior_events)
                if event.tick == tick
                and event.event_type == "offer"
                and event.actor_id == target.agent_id
                and event.target_id == actor.agent_id
                and event.payload.get("item") == action.item
                and event.payload.get("quantity") == action.quantity
                and event.payload.get("price") == action.price
            ),
            None,
        )
        if offer is None:
            return _rejected(world, action, tick, "offer_not_found", prior_events)
        if actor.balance < action.price:
            return _rejected(world, action, tick, "insufficient_balance", prior_events)
        if target.inventory.get(action.item, 0) < action.quantity:
            return _rejected(world, action, tick, "seller_inventory_changed", prior_events)
        agents = []
        for current in world.agents:
            if current.agent_id == actor.agent_id:
                inventory = dict(current.inventory)
                inventory[action.item] = inventory.get(action.item, 0) + action.quantity
                agents.append(replace(current, balance=current.balance - action.price, inventory=inventory))
            elif current.agent_id == target.agent_id:
                inventory = dict(current.inventory)
                inventory[action.item] -= action.quantity
                if inventory[action.item] == 0:
                    del inventory[action.item]
                agents.append(replace(current, balance=current.balance + action.price, inventory=inventory))
            else:
                agents.append(current)
        next_world = _replace_agents(world, agents)
        market = dict(next_world.market)
        market["offers"] = [
            item for item in market.get("offers", []) if item.get("offer_id") != offer.event_id
        ]
        next_world = replace(next_world, market=market)
        return next_world, Event(
            _event_id(tick, action, prior_events), tick, "trade_completed", action.agent_id, target.agent_id,
            {"item": action.item, "quantity": action.quantity, "price": action.price, "offer_id": offer.event_id},
            True, "trade_conservation"
        )

    if action.action_type == "message":
        return world, Event(
            _event_id(tick, action, prior_events), tick, "message", action.agent_id, action.target_id,
            {"text": action.message[:240]}, True, "public_message"
        )

    if action.action_type == "noop":
        return world, Event(
            _event_id(tick, action, prior_events), tick, "noop", action.agent_id, None, {}, True, "no_action"
        )

    return _rejected(world, action, tick, "unsupported_action", prior_events)

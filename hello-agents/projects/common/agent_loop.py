"""A tiny deterministic observe-decide-act loop used in course examples."""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class LoopResult:
    answer: Any
    steps: int
    events: list[dict[str, Any]] = field(default_factory=list)


def run_loop(
    initial_state: Any,
    decide: Callable[[Any], Any],
    act: Callable[[Any, Any], tuple[Any, Any]],
    is_done: Callable[[Any], bool],
    max_steps: int = 5,
) -> LoopResult:
    """Run a bounded loop and record state/action/result events.

    ``act`` returns ``(new_state, answer)``. The answer is returned as soon as
    the state is done; otherwise the last answer is returned at the step limit.
    """
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    state = initial_state
    events: list[dict[str, Any]] = []
    answer: Any = None
    for step in range(1, max_steps + 1):
        action = decide(state)
        state, answer = act(state, action)
        events.append({"step": step, "action": action, "state": state, "answer": answer})
        if is_done(state):
            return LoopResult(answer=answer, steps=step, events=events)
    return LoopResult(answer=answer, steps=max_steps, events=events)

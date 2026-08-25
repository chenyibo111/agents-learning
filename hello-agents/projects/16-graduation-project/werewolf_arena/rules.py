"""权威游戏规则：校验行动、结算阶段和判定胜负。"""

from collections import Counter
from dataclasses import replace
import random

from .schemas import Action, Event, GameState, Phase, PlayerState, Role


# 固定 ID 让离线测试、事件排序和同 seed 重放均保持稳定；真实产品可替换为房间玩家 ID。
PLAYER_IDS = ("alice", "bob", "carol", "david", "eve", "frank")


def initial_game(seed: int = 7) -> GameState:
    """用 seed 打乱固定角色池，创建一局处于首个狼人阶段的游戏。"""
    roles = [Role.WOLF, Role.WOLF, Role.SEER, Role.WITCH, Role.VILLAGER, Role.VILLAGER]
    # 不使用全局随机数，保证同 seed 的身份分配可以精确重放。
    random.Random(seed).shuffle(roles)
    players = []
    for player_id, role in zip(PLAYER_IDS, roles, strict=True):
        # 只有女巫初始拥有两种药物；其他角色的资源标志始终为 False。
        players.append(
            PlayerState(
                player_id=player_id,
                role=role,
                private_memory=("身份信息仅自己可见。",),
                antidote_available=role == Role.WITCH,
                poison_available=role == Role.WITCH,
            )
        )
    return GameState(
        game_id=f"werewolf-{seed}",
        seed=seed,
        round_number=1,
        phase=Phase.NIGHT_WOLF,
        players=tuple(players),
        metrics={
            "model_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model_failures": 0,
            "request_count": 0,
            "fallback_count": 0,
            "noop_count": 0,
            "abstain_count": 0,
            "effective_action_count": 0,
            "invalid_model_output_count": 0,
            "schema_failure_count": 0,
            "invalid_json_count": 0,
        },
    )


def _player(state: GameState, player_id: str | None) -> PlayerState | None:
    """在上帝视角状态中查找玩家；内部规则用 None 表示无效目标。"""
    return next((item for item in state.players if item.player_id == player_id), None)


def _event(
    state: GameState,
    event_type: str,
    payload: dict,
    *,
    public: bool = True,
    recipients: tuple[str, ...] = (),
    rule: str,
) -> Event:
    """基于当前状态生成带稳定 ID、阶段和可见性标签的事件。"""
    return Event(
        event_id=f"r{state.round_number}-{state.phase.value}-e{len(state.events) + 1}-{event_type}",
        round_number=state.round_number,
        phase=state.phase,
        event_type=event_type,
        payload=payload,
        public=public,
        recipients=recipients,
        rule=rule,
    )


def _append_event(state: GameState, event: Event) -> GameState:
    """以不可变方式追加事件，保留所有先前审计轨迹。"""
    return replace(state, events=(*state.events, event))


def _metrics(state: GameState, action: Action) -> GameState:
    """将本次行动携带的模型调用指标累计到全局游戏指标。"""
    metrics = dict(state.metrics)
    metrics["model_calls"] = int(metrics.get("model_calls", 0)) + action.model_calls
    metrics["input_tokens"] = int(metrics.get("input_tokens", 0)) + action.input_tokens
    metrics["output_tokens"] = int(metrics.get("output_tokens", 0)) + action.output_tokens
    metrics["cost_usd"] = round(float(metrics.get("cost_usd", 0.0)) + action.cost_usd, 8)
    metrics["latency_ms"] = int(metrics.get("latency_ms", 0)) + action.latency_ms
    if action.model_calls > 0:
        metrics["request_count"] = int(metrics.get("request_count", 0)) + 1
        if action.action_type == "noop":
            metrics["noop_count"] = int(metrics.get("noop_count", 0)) + 1
        elif action.action_type == "abstain":
            metrics["abstain_count"] = int(metrics.get("abstain_count", 0)) + 1
        else:
            metrics["effective_action_count"] = int(metrics.get("effective_action_count", 0)) + 1
        if action.fallback_reason:
            metrics["fallback_count"] = int(metrics.get("fallback_count", 0)) + 1
        if action.fallback_reason in {"invalid_json", "schema_validation"}:
            metrics["invalid_model_output_count"] = int(metrics.get("invalid_model_output_count", 0)) + 1
        if action.fallback_reason == "schema_validation":
            metrics["schema_failure_count"] = int(metrics.get("schema_failure_count", 0)) + 1
        if action.fallback_reason == "invalid_json":
            metrics["invalid_json_count"] = int(metrics.get("invalid_json_count", 0)) + 1
    if action.decision_label.startswith("llm_"):
        metrics["model_failures"] = int(metrics.get("model_failures", 0)) + 1
    return replace(state, metrics=metrics)


def _reject(state: GameState, action: Action, rule: str) -> GameState:
    """拒绝非法行动，并只把拒绝原因私有回传给提交该行动的玩家。"""
    state = _metrics(state, action)
    return _append_event(
        state,
        _event(
            state,
            "action_rejected",
            {
                "actor_id": action.actor_id,
                "action_type": action.action_type,
                "decision_label": action.decision_label,
                "reason": rule,
            },
            public=False,
            recipients=(action.actor_id,),
            rule=rule,
        ),
    )


def _replace_player(state: GameState, replacement: PlayerState) -> GameState:
    """用新的玩家快照替换旧快照，例如死亡或药物消耗后。"""
    return replace(
        state,
        players=tuple(replacement if item.player_id == replacement.player_id else item for item in state.players),
    )


def _action_for(state: GameState, player_id: str) -> Action | None:
    """读取该玩家在当前阶段已经提交、但尚未结算的一次行动。"""
    return next((item for item in state.pending_actions if item.actor_id == player_id), None)


def _alive_target(state: GameState, target_id: str | None, actor_id: str, *, allow_self: bool = False) -> bool:
    """校验目标存在、存活，并按规则决定是否允许选择自己。"""
    target = _player(state, target_id)
    return target is not None and target.alive and (allow_self or target.player_id != actor_id)


def _validate_action(state: GameState, action: Action) -> str | None:
    """返回 None 表示合法；否则返回稳定规则码供事件和测试使用。"""
    actor = _player(state, action.actor_id)
    # 这些通用检查先执行，避免进入角色分支后才发现游戏已结束或玩家已死亡。
    if state.status != "RUNNING":
        return "game_not_running"
    if actor is None:
        return "unknown_actor"
    if not actor.alive:
        return "dead_player_cannot_act"
    if _action_for(state, actor.player_id) is not None:
        return "duplicate_action"
    # noop 是 Policy/模型失败后的安全无动作，所有阶段都允许提交并由结算器自然跳过。
    if action.action_type == "noop":
        return None
    if state.phase == Phase.NIGHT_WOLF:
        # 夜间第一阶段仅狼人可私密发言；保留 wolf_kill 作为旧 checkpoint/测试的兼容输入。
        if actor.role != Role.WOLF:
            return "role_cannot_act"
        if action.action_type == "wolf_speak":
            if action.target_id is not None:
                return "non_speech_target_not_null"
            return None if len(action.speech) <= 240 else "speech_too_long"
        if action.action_type == "wolf_kill":
            target = _player(state, action.target_id)
            if target is None or not target.alive or target.role == Role.WOLF:
                return "invalid_target"
            return None
        return "invalid_phase_action"
    if state.phase == Phase.NIGHT_WOLF_CONFIRM:
        # 狼人确认投票独立提交；规则只在结算阶段公开票型并决定是否形成袭击。
        if actor.role != Role.WOLF:
            return "role_cannot_act"
        if action.action_type != "wolf_vote":
            return "invalid_phase_action"
        target = _player(state, action.target_id)
        if target is None or not target.alive or target.role == Role.WOLF:
            return "invalid_target"
        return None
    if state.phase == Phase.NIGHT_SEER:
        # 预言家每晚只能查验一次其他存活玩家。
        if actor.role != Role.SEER:
            return "role_cannot_act"
        if action.action_type != "inspect":
            return "invalid_phase_action"
        return None if _alive_target(state, action.target_id, actor.player_id) else "invalid_target"
    if state.phase == Phase.NIGHT_WITCH:
        # 女巫通过“每阶段只能提交一次 Action”保证同晚不能同时救人与毒人。
        if actor.role != Role.WITCH:
            return "role_cannot_act"
        if action.action_type == "noop":
            return None
        if action.action_type == "witch_save":
            if not actor.antidote_available:
                return "antidote_unavailable"
            if state.night_victim is None:
                return "no_attack_to_save"
            return None if action.target_id == state.night_victim else "invalid_save_target"
        if action.action_type == "witch_poison":
            if not actor.poison_available:
                return "poison_unavailable"
            return None if _alive_target(state, action.target_id, actor.player_id) else "invalid_target"
        return "invalid_phase_action"
    if state.phase == Phase.DAY_DISCUSSION:
        # 发言长度限制是最基础的上下文与成本控制措施。
        if action.action_type != "speak":
            return "invalid_phase_action"
        return None if len(action.speech) <= 240 else "speech_too_long"
    if state.phase == Phase.DAY_VOTE:
        # 投票允许弃票，但有效投票不能投自己或死亡玩家。
        if action.action_type == "abstain":
            return None
        if action.action_type != "vote":
            return "invalid_phase_action"
        return None if _alive_target(state, action.target_id, actor.player_id) else "invalid_target"
    return "invalid_phase"


def submit_action(state: GameState, action: Action) -> GameState:
    """记录经过校验的玩家意图；结算只能由 advance_phase 完成。"""
    # 先校验、后记录；非法 Action 永远不会进入 pending_actions。
    reason = _validate_action(state, action)
    if reason:
        return _reject(state, action, reason)
    # 合法或非法模型调用都应计入成本，避免失败调用在报表中“消失”。
    state = _metrics(state, action)
    state = replace(state, pending_actions=(*state.pending_actions, action))
    if action.action_type == "speak":
        # 发言在提交时立即公开，因此后续发言者可以基于前序发言作回应。
        state = _append_event(
            state,
            _event(
                state,
                "speech",
                {"speaker": action.actor_id, "text": action.speech},
                rule="public_discussion",
            ),
        )
    elif action.action_type == "wolf_speak":
        wolves = tuple(player.player_id for player in state.players if player.alive and player.role == Role.WOLF)
        state = _append_event(
            state,
            _event(
                state,
                "wolf_negotiation_message",
                {"speaker": action.actor_id, "text": action.speech},
                public=False,
                recipients=wolves,
                rule="private_wolf_negotiation",
            ),
        )
    # 投票行动暂存到 pending_actions；所有玩家完成投票后才由结算阶段一次性公开票型。
    return state


def _finish_if_winner(state: GameState) -> GameState:
    """每次造成死亡后立即检查阵营胜负，并在结束时锁定后续行动。"""
    winner = check_winner(state)
    if winner is None:
        return state
    state = replace(state, phase=Phase.FINISHED, status="COMPLETED", winner=winner, pending_actions=())
    return _append_event(state, _event(state, "game_finished", {"winner": winner}, rule="victory_condition"))


def check_winner(state: GameState) -> str | None:
    """按存活阵营数量返回胜者；尚未结束时返回 None。"""
    wolves = sum(player.alive and player.role == Role.WOLF for player in state.players)
    good = sum(player.alive and player.role != Role.WOLF for player in state.players)
    if wolves == 0:
        return "good"
    if wolves >= good:
        return "wolves"
    return None


def _resolve_legacy_wolf_phase(state: GameState) -> GameState:
    """兼容旧版直接提交 wolf_kill 的状态；新流程使用确认投票。"""
    wolves = [player.player_id for player in state.players if player.alive and player.role == Role.WOLF]
    targets = [_action_for(state, wolf).target_id for wolf in wolves if _action_for(state, wolf)]
    # 缺行动、只剩一狼以外的异常或目标不一致都会被视为本晚袭击失败。
    night_victim = targets[0] if len(targets) == len(wolves) and len(set(targets)) == 1 else None
    witch = next((player.player_id for player in state.players if player.alive and player.role == Role.WITCH), None)
    recipients = tuple(wolves + ([witch] if witch else []))
    # 此事件是私有的：狼人知道协作结果，存活女巫才能在下一阶段获知袭击目标。
    event = _event(
        state,
        "wolf_target_selected" if night_victim else "wolf_attack_failed",
        {"target": night_victim},
        public=False,
        recipients=recipients,
        rule="matched_wolf_target" if night_victim else "wolf_disagreement",
    )
    state = replace(state, night_victim=night_victim, pending_actions=(), phase=Phase.NIGHT_SEER)
    return _append_event(state, event)


def _resolve_wolf_talk_phase(state: GameState) -> GameState:
    """结算狼人私密发言，进入隐藏的最终确认投票阶段。"""
    if any(action.action_type == "wolf_kill" for action in state.pending_actions):
        return _resolve_legacy_wolf_phase(state)
    return replace(state, pending_actions=(), phase=Phase.NIGHT_WOLF_CONFIRM)


def _resolve_wolf_phase(state: GameState) -> GameState:
    """汇总狼人确认票：完全一致才产生可被女巫看到的夜袭目标。"""
    wolves = [player.player_id for player in state.players if player.alive and player.role == Role.WOLF]
    ballots = {
        wolf: (
            _action_for(state, wolf).target_id
            if _action_for(state, wolf) is not None and _action_for(state, wolf).action_type == "wolf_vote"
            else None
        )
        for wolf in wolves
    }
    targets = [target for target in ballots.values() if target]
    counts = Counter(targets)
    consensus = len(targets) == len(wolves) and len(counts) == 1
    night_victim = targets[0] if consensus else None
    state = _append_event(
        state,
        _event(
            state,
            "wolf_vote_revealed",
            {"ballots": dict(sorted(ballots.items())), "counts": dict(sorted(counts.items())), "consensus": consensus},
            public=False,
            recipients=tuple(wolves),
            rule="wolf_confirm_reveal",
        ),
    )
    witch = next((player.player_id for player in state.players if player.alive and player.role == Role.WITCH), None)
    recipients = tuple(wolves + ([witch] if witch else []))
    result_event = _event(
        state,
        "wolf_target_selected" if night_victim else "wolf_attack_failed",
        {"target": night_victim},
        public=False,
        recipients=recipients,
        rule="matched_wolf_target" if night_victim else "wolf_disagreement",
    )
    state = replace(state, night_victim=night_victim, pending_actions=(), phase=Phase.NIGHT_SEER)
    return _append_event(state, result_event)


def _resolve_seer_phase(state: GameState) -> GameState:
    """结算预言家查验，并把狼人/好人结论仅单播给预言家。"""
    seer = next((player for player in state.players if player.alive and player.role == Role.SEER), None)
    action = _action_for(state, seer.player_id) if seer else None
    if action is None or seer is None or action.action_type != "inspect":
        # 预言家死亡或未行动时，安静跳过，不为其他玩家制造额外信息。
        return replace(state, pending_actions=(), phase=Phase.NIGHT_WITCH)
    target = _player(state, action.target_id)
    # 规则引擎读取真实身份；Policy 不会接触到 target.role。
    alignment = "werewolf" if target and target.role == Role.WOLF else "good"
    event = _event(
        state,
        "inspection_result",
        {"target": action.target_id, "alignment": alignment},
        public=False,
        recipients=(seer.player_id,),
        rule="seer_inspection",
    )
    state = replace(state, pending_actions=(), phase=Phase.NIGHT_WITCH)
    return _append_event(state, event)


def _resolve_witch_phase(state: GameState) -> GameState:
    """消耗女巫药物、结算夜晚死亡，并发布不含身份的夜间公告。"""
    witch = next((player for player in state.players if player.alive and player.role == Role.WITCH), None)
    action = _action_for(state, witch.player_id) if witch else None
    # 女巫只有一个 Action；因此 saved 与 poison_target 不可能同时为真。
    saved = action is not None and action.action_type == "witch_save"
    poison_target = action.target_id if action is not None and action.action_type == "witch_poison" else None
    if witch and saved:
        # 解药只改变本晚袭击结果，不公开是谁使用了药。
        state = _replace_player(state, replace(witch, antidote_available=False))
        state = _append_event(
            state,
            _event(state, "night_saved", {"target": state.night_victim}, public=False, recipients=(witch.player_id,), rule="witch_antidote"),
        )
    if witch and poison_target:
        # 毒药产生额外死亡，但使用记录保持为女巫私有事件。
        state = _replace_player(state, replace(witch, poison_available=False))
        state = _append_event(
            state,
            _event(state, "night_poisoned", {"target": poison_target}, public=False, recipients=(witch.player_id,), rule="witch_poison"),
        )
    # 用集合去重：理论上毒药可能选中夜袭目标，结算时只能死亡一次。
    victims = set()
    if state.night_victim and not saved:
        victims.add(state.night_victim)
    if poison_target:
        victims.add(poison_target)
    for victim_id in victims:
        victim = _player(state, victim_id)
        if victim and victim.alive:
            state = _replace_player(state, replace(victim, alive=False))
    # 白天只公布死亡名单，不公布死亡玩家的真实身份或药物来源。
    announcement = _event(state, "night_announcement", {"deaths": sorted(victims)}, rule="night_resolution")
    state = replace(state, pending_actions=(), night_victim=None, phase=Phase.DAY_DISCUSSION)
    state = _append_event(state, announcement)
    return _finish_if_winner(state)


def _resolve_vote_phase(state: GameState) -> GameState:
    """隐藏收集投票，完成后公开票型并按唯一最高票结算。"""
    ballots = {
        action.actor_id: action.target_id
        for action in state.pending_actions
        if action.action_type in {"vote", "abstain"}
    }
    votes = [target_id for target_id in ballots.values() if target_id]
    # abstain 不进入票数统计；空票数也会走平票/无人出局分支。
    counts = Counter(votes)
    top = [player_id for player_id, count in counts.items() if count == max(counts.values())] if counts else []
    state = replace(state, pending_actions=())
    state = _append_event(
        state,
        _event(
            state,
            "vote_revealed",
            {
                "ballots": dict(sorted(ballots.items())),
                "counts": dict(sorted(counts.items())),
            },
            rule="vote_reveal_after_submission",
        ),
    )
    if len(top) == 1:
        # 唯一最高票才会产生执行，避免并列票数时引擎任意挑选受害者。
        executed = _player(state, top[0])
        if executed:
            state = _replace_player(state, replace(executed, alive=False))
        state = _append_event(state, _event(state, "execution", {"player_id": top[0]}, rule="majority_vote"))
    else:
        # 票型本身公开，便于后续 Agent 从历史投票推理身份。
        state = _append_event(state, _event(state, "vote_tied", {"votes": dict(sorted(counts.items()))}, rule="tied_vote"))
    state = _finish_if_winner(state)
    if state.status == "RUNNING":
        # 没有胜者时开始下一轮夜晚，并清理本轮暂存行动。
        state = replace(state, phase=Phase.NIGHT_WOLF, round_number=state.round_number + 1, night_victim=None)
    return state


def advance_phase(state: GameState) -> GameState:
    """按当前阶段调用唯一对应的结算函数；这是状态机推进的唯一出口。"""
    if state.status != "RUNNING":
        return state
    if state.phase == Phase.NIGHT_WOLF:
        return _resolve_wolf_talk_phase(state)
    if state.phase == Phase.NIGHT_WOLF_CONFIRM:
        return _resolve_wolf_phase(state)
    if state.phase == Phase.NIGHT_SEER:
        return _resolve_seer_phase(state)
    if state.phase == Phase.NIGHT_WITCH:
        return _resolve_witch_phase(state)
    if state.phase == Phase.DAY_DISCUSSION:
        return replace(state, phase=Phase.DAY_VOTE, pending_actions=())
    if state.phase == Phase.DAY_VOTE:
        return _resolve_vote_phase(state)
    return state


def finish_draw(state: GameState) -> GameState:
    """达到运行时最大轮数后结束为平局，防止 Agent 无限消耗资源。"""
    if state.status != "RUNNING":
        return state
    state = replace(state, phase=Phase.FINISHED, status="DRAW", winner="draw", pending_actions=())
    return _append_event(state, _event(state, "game_finished", {"winner": "draw"}, rule="max_rounds"))

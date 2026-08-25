"""将公开游戏事件转换为不泄露身份的玩家可读叙事。"""

from collections.abc import Iterable

from .schemas import Event


_PRIVATE_EVENT_TYPES = {
    "action_rejected",
    "inspection_result",
    "night_saved",
    "night_poisoned",
    "wolf_negotiation_message",
    "wolf_vote_revealed",
    "wolf_target_selected",
    "wolf_attack_failed",
}

_WINNER_LABELS = {"good": "好人阵营", "wolves": "狼人阵营", "draw": "平局"}


def _names(values: object) -> str:
    """稳定格式化玩家 ID 列表；异常 payload 不应让观战页崩溃。"""
    if not isinstance(values, (list, tuple, set)):
        return ""
    return "、".join(str(value) for value in sorted(values))


def narrate_event(event: Event) -> str | None:
    """把单个公开 Event 转成短叙事；私有或敏感事件返回 None。"""
    if not event.public or event.event_type in _PRIVATE_EVENT_TYPES:
        return None
    payload = event.payload if isinstance(event.payload, dict) else {}
    event_type = event.event_type
    if event_type == "speech":
        speaker = str(payload.get("speaker", "玩家"))
        text = str(payload.get("text", ""))
        return f"{speaker}：{text}"
    if event_type == "night_announcement":
        deaths = _names(payload.get("deaths", []))
        return f"天亮了。昨夜出局：{deaths}。" if deaths else "天亮了。昨夜无人出局。"
    if event_type == "vote_revealed":
        ballots = payload.get("ballots", {})
        counts = payload.get("counts", {})
        ballot_text = "、".join(
            f"{voter}→{target or '弃票'}"
            for voter, target in sorted(ballots.items())
        ) if isinstance(ballots, dict) else ""
        count_text = "、".join(
            f"{target} {count}票"
            for target, count in sorted(counts.items())
        ) if isinstance(counts, dict) else ""
        return f"投票结果：{ballot_text}。总票数：{count_text or '无人得票'}。"
    if event_type == "execution":
        return f"投票结束，{payload.get('player_id', '一名玩家')} 被放逐。"
    if event_type == "vote_tied":
        return "最高票并列，本轮无人出局。"
    if event_type == "game_finished":
        return f"游戏结束，{_WINNER_LABELS.get(str(payload.get('winner')), '结果待定')}获胜。"
    if event_type == "phase_started":
        return f"进入第 {event.round_number} 轮：{payload.get('label', '新阶段')}。"
    return f"第 {event.round_number} 轮发生公开事件：{event_type}。"


def render_public_events(events: Iterable[Event]) -> list[str]:
    """按事件顺序返回公开叙事；私有事件完全不会进入结果。"""
    return [text for event in events if (text := narrate_event(event)) is not None]

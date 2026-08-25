"""生成仅供开发者和裁判使用的完整上帝视角页面。"""

from collections import Counter
from html import escape
import json
import re

from .schemas import GameState, Phase


_PHASE_LABELS = {
    Phase.NIGHT_WOLF: "狼人私密协商",
    Phase.NIGHT_WOLF_CONFIRM: "狼人确认投票",
    Phase.NIGHT_SEER: "预言家查验",
    Phase.NIGHT_WITCH: "女巫行动",
    Phase.DAY_DISCUSSION: "白天讨论",
    Phase.DAY_VOTE: "白天投票",
    Phase.FINISHED: "游戏结束",
}
_ROLE_LABELS = {
    "wolf": "狼人",
    "seer": "预言家",
    "witch": "女巫",
    "villager": "村民",
}


def _safe(value: object) -> str:
    """把任何动态值作为纯文本安全嵌入 HTML。"""
    return escape(str(value), quote=True)


def _json_text(value: object) -> str:
    """把审计数据格式化为稳定 JSON 文本，异常对象也不会阻断页面生成。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def _dom_id(value: str) -> str:
    """将事件 ID 限制为安全、稳定的 DOM id。"""
    return re.sub(r"[^A-Za-z0-9_-]", "-", value)


def _event_summary(event: object) -> str:
    """提取短摘要；详细 payload 在右侧审计面板中保留。"""
    payload = getattr(event, "payload", {})
    if not isinstance(payload, dict):
        return ""
    parts = []
    for key in ("speaker", "target", "player_id", "action_type", "alignment", "winner"):
        if key in payload:
            parts.append(f"{key}={payload[key]}")
    if not parts and payload:
        parts.append(f"字段数={len(payload)}")
    return " · ".join(parts)


def _render_event(event: object) -> tuple[str, str]:
    """返回时间线卡片和对应的右侧诊断详情。"""
    event_id = str(event.event_id)
    dom_id = _dom_id(event_id)
    visibility = "公开" if event.public else "私有"
    visibility_class = "public" if event.public else "private"
    phase = _PHASE_LABELS.get(event.phase, event.phase.value)
    recipients = ", ".join(event.recipients) or "无"
    payload_json = _json_text(event.payload)
    card = f"""<article class="event-card {visibility_class}" data-event-id="{_safe(event_id)}" data-inspect-id="inspect-{_safe(dom_id)}">
  <div class="event-meta"><span class="round">R{_safe(event.round_number)}</span><span class="phase">{_safe(phase)}</span><span class="visibility {visibility_class}">{_safe(visibility)}</span></div>
  <div class="event-main"><strong>{_safe(event.event_type)}</strong><span class="event-id">{_safe(event_id)}</span><p>{_safe(_event_summary(event) or "无摘要")}</p></div>
</article>"""
    detail = f"""<section class="inspector-detail" id="inspect-{_safe(dom_id)}" data-event-detail>
  <div class="detail-title"><strong>{_safe(event.event_type)}</strong><span>{_safe(visibility)} · {_safe(event.rule or "无规则标签")}</span></div>
  <dl class="detail-list"><dt>event_id</dt><dd>{_safe(event_id)}</dd><dt>round / phase</dt><dd>R{_safe(event.round_number)} / {_safe(phase)}</dd><dt>recipients</dt><dd>{_safe(recipients)}</dd><dt>public</dt><dd>{_safe(event.public)}</dd></dl>
  <h4>payload</h4><pre>{_safe(payload_json)}</pre>
</section>"""
    return card, detail


def render_god_view_html(state: GameState) -> str:
    """从完整 GameState 生成自包含审计页面，不注入完整状态 JavaScript 对象。"""
    event_cards = []
    event_details = []
    for event in state.events:
        card, detail = _render_event(event)
        event_cards.append(card)
        event_details.append(detail)
    timeline_html = "\n".join(event_cards) or '<p class="empty">暂无事件。</p>'
    details_html = "\n".join(event_details) or '<p class="empty">请选择事件查看诊断。</p>'
    counts = Counter(event.event_type for event in state.events)
    rejection_count = counts["action_rejected"]
    alive_count = sum(player.alive for player in state.players)
    winner = {"good": "好人阵营", "wolves": "狼人阵营", "draw": "平局"}.get(state.winner or "", "进行中")
    phase = _PHASE_LABELS.get(state.phase, state.phase.value)
    player_html = "\n".join(
        f'<li class="player-card {"alive" if player.alive else "dead"}"><div><strong>{_safe(player.player_id)}</strong><span>{_safe(_ROLE_LABELS.get(player.role.value, player.role.value))} · {_safe(player.role.value)}</span></div><small>{"存活" if player.alive else "已出局"}<br>解药：{_safe(player.antidote_available)} · 毒药：{_safe(player.poison_available)}</small></li>'
        for player in state.players
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>狼人杀上帝视角 · {_safe(state.game_id)}</title>
<style>
:root {{ color-scheme:dark; font-family:Inter,system-ui,sans-serif; background:#080d18; color:#e5e7eb; }}
body {{ margin:0; min-height:100vh; background:radial-gradient(circle at 12% 0%,#1b2d50,#080d18 52%); }}
.shell {{ max-width:1280px; margin:0 auto; padding:30px 20px 56px; }}
.hero {{ display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:22px; }}
.kicker {{ color:#7dd3fc; font-size:11px; font-weight:800; letter-spacing:.16em; }}
h1 {{ margin:6px 0; font-size:clamp(28px,4vw,46px); letter-spacing:-.04em; }}
.subtitle,.muted {{ margin:0; color:#94a3b8; }}
.badge {{ border:1px solid #7c3aed; border-radius:999px; padding:10px 14px; color:#d8b4fe; background:#24144a; font-size:12px; font-weight:800; white-space:nowrap; }}
.stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:18px; }}
.stat,.panel {{ border:1px solid #263b60; border-radius:18px; background:rgba(15,23,42,.86); box-shadow:0 18px 55px rgba(0,0,0,.18); }}
.stat {{ padding:14px; }}
.stat small {{ display:block; color:#94a3b8; font-size:11px; margin-bottom:6px; }}
.stat strong {{ color:#f8fafc; font-size:18px; }}
.stat em {{ color:#34d399; font-style:normal; font-size:11px; margin-left:5px; }}
.layout {{ display:grid; grid-template-columns:minmax(0,1.35fr) minmax(340px,.8fr); gap:16px; }}
.panel {{ padding:17px; }}
.panel-head {{ display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:14px; }}
.panel h2 {{ margin:0; color:#f8fafc; font-size:16px; }}
.timeline {{ display:grid; gap:9px; max-height:720px; overflow:auto; padding-right:3px; }}
.event-card {{ display:grid; grid-template-columns:138px 1fr; gap:12px; align-items:start; padding:13px; border:1px solid #243858; border-radius:13px; background:linear-gradient(90deg,#16233a,#0f192b); cursor:pointer; transition:border-color .16s,transform .16s; }}
.event-card:hover,.event-card.selected {{ border-color:#38bdf8; transform:translateY(-1px); }}
.event-card.private {{ border-left:3px solid #fb7185; }}
.event-card.public {{ border-left:3px solid #34d399; }}
.event-meta {{ display:flex; flex-wrap:wrap; gap:5px; align-items:center; }}
.round,.phase,.visibility {{ font-size:11px; }}
.round {{ color:#60a5fa; font-weight:800; }} .phase {{ color:#c4b5fd; }}
.visibility {{ border-radius:999px; padding:2px 6px; }} .visibility.public {{ color:#6ee7b7; background:#063b2c; }} .visibility.private {{ color:#fda4af; background:#4b1322; }}
.event-main strong {{ display:block; color:#e2e8f0; font-size:13px; }}
.event-id {{ color:#64748b; font:10px ui-monospace,monospace; }}
.event-main p {{ margin:5px 0 0; color:#94a3b8; font-size:12px; line-height:1.5; word-break:break-word; }}
.side {{ display:grid; align-content:start; gap:14px; }}
.players {{ list-style:none; padding:0; margin:0; display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.player-card {{ display:flex; justify-content:space-between; gap:8px; padding:10px; border:1px solid #243858; border-radius:11px; background:#111c31; }}
.player-card.dead {{ opacity:.56; }} .player-card strong {{ display:block; color:#e2e8f0; font-size:12px; }} .player-card span,.player-card small {{ color:#94a3b8; font-size:10px; line-height:1.45; }}
.detail-title {{ display:flex; justify-content:space-between; gap:8px; margin-bottom:10px; }} .detail-title strong {{ color:#fbbf24; }} .detail-title span {{ color:#94a3b8; font-size:10px; }}
.detail-list {{ display:grid; grid-template-columns:110px 1fr; gap:5px; margin:0 0 12px; font-size:11px; }} .detail-list dt {{ color:#64748b; }} .detail-list dd {{ margin:0; color:#cbd5e1; word-break:break-word; }}
.inspector-detail {{ display:none; }} .inspector-detail.active {{ display:block; }} .inspector h2 {{ margin:0 0 13px; font-size:15px; }} .inspector h4 {{ margin:10px 0 6px; color:#94a3b8; font-size:11px; text-transform:uppercase; letter-spacing:.08em; }}
pre {{ margin:0; max-height:300px; overflow:auto; padding:11px; border-radius:11px; background:#08101d; border:1px solid #21304a; color:#93c5fd; font:11px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; white-space:pre-wrap; }}
.empty {{ color:#64748b; padding:18px 0; }}
@media(max-width:820px) {{ .hero,.layout {{ display:block; }} .badge {{ display:inline-block; margin-top:14px; }} .stats {{ grid-template-columns:1fr 1fr; }} .side {{ margin-top:16px; }} }}
</style></head>
<body><main class="shell">
<header class="hero"><div><div class="kicker">WEREWOLF ARENA · DEBUG CONSOLE</div><h1>第 {_safe(state.round_number)} 轮 · {_safe(phase)}</h1><p class="subtitle">{_safe(state.game_id)} · seed {_safe(state.seed)} · 事件 {_safe(len(state.events))} 条 · {_safe(state.status)}</p></div><div class="badge">上帝视角 · 仅开发/裁判</div></header>
<section class="stats"><div class="stat"><small>当前阶段</small><strong>{_safe(phase)}</strong><em>{_safe(state.status)}</em></div><div class="stat"><small>存活玩家</small><strong>{_safe(alive_count)} / {_safe(len(state.players))}</strong><em>{_safe(winner)}</em></div><div class="stat"><small>夜袭目标</small><strong>{_safe(state.night_victim or "无")}</strong><em>完整状态</em></div><div class="stat"><small>规则拒绝</small><strong>{_safe(rejection_count)}</strong><em>{"合规" if rejection_count == 0 else "需检查"}</em></div></section>
<div class="layout"><section class="panel"><div class="panel-head"><h2>完整事件时间线</h2><span class="muted">公开与私有事件均展示 · 点击查看诊断</span></div><div class="timeline">{timeline_html}</div></section>
<aside class="side"><section class="panel"><div class="panel-head"><h2>玩家与身份</h2><span class="muted">完整状态</span></div><ul class="players">{player_html}</ul></section><section class="panel inspector"><h2>事件规则诊断</h2>{details_html}</section></aside></div>
</main><script>
const cards = document.querySelectorAll('.event-card');
const details = document.querySelectorAll('[data-event-detail]');
function selectEvent(card) {{
  cards.forEach(item => item.classList.remove('selected'));
  details.forEach(item => item.classList.remove('active'));
  card.classList.add('selected');
  const detail = document.getElementById(card.dataset.inspectId);
  if (detail) detail.classList.add('active');
}}
cards.forEach(card => card.addEventListener('click', () => selectEvent(card)));
if (cards[0]) selectEvent(cards[0]);
</script></body></html>"""

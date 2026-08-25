"""生成不含上帝视角信息的静态剧场型观战页面。"""

from html import escape

from .narrative import narrate_event
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


def _safe(value: object) -> str:
    """统一转义动态文字，公开发言也只能作为纯文本渲染。"""
    return escape(str(value), quote=True)


def render_spectator_html(state: GameState) -> str:
    """从公开事件和存活状态生成自包含 HTML，不序列化完整 GameState。"""
    timeline = [
        (event, text)
        for event in state.events
        if (text := narrate_event(event)) is not None
    ]
    timeline_html = "\n".join(
        f'<li class="timeline-item"><span class="round">R{_safe(event.round_number)}</span><span class="phase">{_safe(_PHASE_LABELS.get(event.phase, event.phase.value))}</span><span>{_safe(text)}</span></li>'
        for event, text in timeline
    ) or '<li class="empty">暂时还没有公开事件。</li>'
    player_html = "\n".join(
        f'<li class="player {"alive" if player.alive else "dead"}"><span class="dot"></span>{_safe(player.player_id)}<small>{"存活" if player.alive else "已出局"}</small></li>'
        for player in state.players
    )
    phase = _PHASE_LABELS.get(state.phase, state.phase.value)
    winner = {"good": "好人阵营", "wolves": "狼人阵营", "draw": "平局"}.get(state.winner or "", "进行中")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>狼人杀观战 · {_safe(state.game_id)}</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background:#0b1020; color:#e5e7eb; }}
body {{ margin:0; background:radial-gradient(circle at top,#1b2947,#0b1020 58%); min-height:100vh; }}
.shell {{ max-width:1100px; margin:0 auto; padding:32px 20px 56px; }}
.hero {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:22px; }}
h1 {{ margin:0 0 8px; font-size:clamp(26px,4vw,46px); letter-spacing:-.04em; }}
.subtitle {{ color:#94a3b8; margin:0; }}
.status {{ border:1px solid #334155; border-radius:14px; padding:12px 16px; background:#111a2d; min-width:160px; }}
.status strong {{ display:block; color:#93c5fd; margin-bottom:4px; }}
.layout {{ display:grid; grid-template-columns:minmax(0,1fr) 260px; gap:18px; }}
.panel {{ background:rgba(15,23,42,.9); border:1px solid #263754; border-radius:18px; padding:18px; box-shadow:0 18px 50px rgba(0,0,0,.18); }}
.panel h2 {{ margin:0 0 15px; font-size:17px; }}
.timeline {{ list-style:none; padding:0; margin:0; display:grid; gap:10px; }}
.timeline-item {{ display:flex; gap:12px; padding:14px; border-radius:12px; background:#17233a; line-height:1.6; white-space:pre-wrap; }}
.round {{ color:#60a5fa; min-width:30px; font-size:12px; font-weight:800; }}
.phase {{ color:#a78bfa; min-width:84px; font-size:12px; }}
.empty {{ color:#64748b; padding:18px 0; }}
.players {{ list-style:none; padding:0; margin:0; display:grid; gap:8px; }}
.player {{ display:flex; align-items:center; gap:8px; border-radius:10px; padding:10px; background:#17233a; }}
.player.dead {{ opacity:.45; }}
.player small {{ margin-left:auto; color:#94a3b8; }}
.dot {{ width:8px; height:8px; border-radius:99px; background:#34d399; }}
.dead .dot {{ background:#64748b; }}
.privacy {{ margin-top:18px; color:#c4b5fd; border:1px dashed #7c3aed; border-radius:12px; padding:12px; font-size:12px; line-height:1.6; }}
@media (max-width:760px) {{ .hero,.layout {{ display:block; }} .status {{ margin-top:16px; }} .panel + .panel {{ margin-top:18px; }} }}
</style></head>
<body><main class="shell">
<header class="hero"><div><h1>WEREWOLF ARENA</h1><p class="subtitle">剧场叙事观战回放 · {_safe(state.game_id)}</p></div>
<div class="status"><strong>第 {_safe(state.round_number)} 轮 · {_safe(phase)}</strong><span>{_safe(winner)}</span></div></header>
<div class="layout"><section class="panel"><h2>公开时间线</h2><ol class="timeline">{timeline_html}</ol></section>
<aside class="panel"><h2>玩家状态</h2><ul class="players">{player_html}</ul><div class="privacy">观战页只展示公开事件。身份、狼人协商、预言家查验和女巫私有信息不会出现在此页面。</div></aside></div>
</main></body></html>"""

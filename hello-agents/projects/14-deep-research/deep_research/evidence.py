"""从原始来源构造证据、结论和引用候选。"""

from collections import defaultdict

from .schemas import Claim, Evidence, Source


def extract_evidence(sources: list[Source] | tuple[Source, ...]) -> tuple[Evidence, ...]:
    return tuple(
        Evidence(
            evidence_id=f"{source.source_id}-E1",
            source_id=source.source_id,
            chunk_id="chunk-1",
            quote=source.content,
            topic=source.topic,
            stance=source.stance,
        )
        for source in sources
    )


def build_claims(evidence: list[Evidence] | tuple[Evidence, ...]) -> tuple[Claim, ...]:
    grouped: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.topic].append(item)
    claims: list[Claim] = []
    for topic, items in sorted(grouped.items()):
        if topic == "agent_state":
            text = "Agent 通常由模型、工具和状态组成"
        elif topic == "offline_eval":
            text = "离线数据可以用于回归测试和发布前评估"
        else:
            text = f"研究主题 {topic} 有可用证据"
        has_support = any(item.stance == "supports" for item in items)
        has_conflict = has_support and any(item.stance == "contradicts" for item in items)
        claims.append(
            Claim(
                claim_id=f"C-{topic}",
                text=text,
                evidence_ids=tuple(item.evidence_id for item in items),
                confidence=0.5 if has_conflict else (0.9 if has_support else 0.3),
                uncertain=has_conflict,
            )
        )
    return tuple(claims)

"""研究问题拆解和预算辅助函数。"""

from .schemas import ResearchQuery


def decompose_question(query: ResearchQuery) -> tuple[str, ...]:
    return (
        f"{query.question} 的核心概念和状态机制",
        f"{query.question} 的评测证据和回归方法",
    )

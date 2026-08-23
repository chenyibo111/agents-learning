"""用统一数据结构比较不同 Agent 范式的表示方式、反馈和限制。"""

import argparse
from dataclasses import asdict, dataclass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


@dataclass(frozen=True)
class Stage:
    """一个历史阶段的最小比较记录。"""

    year: int
    name: str
    representation: str
    feedback: str
    limitation: str
    failure_case: str


STAGES = [
    Stage(
        year=1950,
        name="符号主义与规则",
        representation="显式规则与逻辑符号",
        feedback="人工编写的事实和规则",
        limitation="可解释但覆盖有限，难以处理开放表达",
        failure_case="用户换一种说法，系统没有匹配到对应规则",
    ),
    Stage(
        year=1970,
        name="专家系统",
        representation="领域知识库与推理机",
        feedback="专家知识和人工维护的规则",
        limitation="知识获取和维护成本高，容易陷入封闭领域",
        failure_case="遇到知识库没有覆盖的新故障，系统无法推理",
    ),
    Stage(
        year=1990,
        name="搜索与规划",
        representation="状态、动作、目标和路径代价",
        feedback="状态转移、目标是否达成和路径代价",
        limitation="动作和状态增多时，组合空间可能爆炸",
        failure_case="每一步都有很多动作，搜索在有限时间内找不到方案",
    ),
    Stage(
        year=1990,
        name="概率模型",
        representation="概率分布与不确定性",
        feedback="带噪声的观测数据和统计证据",
        limitation="依赖数据和统计假设，分布变化会降低可靠性",
        failure_case="线上数据分布变化，原来的概率估计不再准确",
    ),
    Stage(
        year=2010,
        name="深度学习",
        representation="神经网络参数与数据中的模式",
        feedback="标注数据和训练损失",
        limitation="需要大量高质量数据，内部决策不容易解释",
        failure_case="训练集有偏，模型把数据偏差当成了通用规律",
    ),
    Stage(
        year=2010,
        name="强化学习",
        representation="状态、动作和可学习策略",
        feedback="环境奖励、惩罚和长期回报",
        limitation="奖励难设计，真实环境中的试错成本和风险较高",
        failure_case="奖励函数有漏洞，策略只优化指标而没有完成真实目标",
    ),
    Stage(
        year=2017,
        name="Transformer",
        representation="序列上下文和注意力关系",
        feedback="大规模语料上的预测损失",
        limitation="本身只是模型架构，不提供目标、权限和行动运行时",
        failure_case="模型能生成流畅文本，但没有工具和状态就无法完成外部任务",
    ),
    Stage(
        year=2020,
        name="LLM Agent",
        representation="自然语言上下文、工具和任务状态",
        feedback="工具 observation、用户反馈和运行时事件",
        limitation="需要处理幻觉、权限、成本、超时和循环风险",
        failure_case="模型选择了错误工具或参数，运行时必须拒绝或安全回传错误",
    ),
]


def timeline_data() -> list[dict[str, object]]:
    """返回可序列化的时间线数据，便于测试、展示和后续扩展。"""
    return [asdict(stage) for stage in STAGES]


def render_timeline(*, include_failures: bool = False) -> str:
    """渲染历史阶段的比较结果。"""
    lines: list[str] = []
    for stage in STAGES:
        line = (
            f"{stage.year} {stage.name}: "
            f"表示={stage.representation}；"
            f"反馈={stage.feedback}；"
            f"限制={stage.limitation}"
        )
        if include_failures:
            line += f"；失败案例={stage.failure_case}"
        lines.append(line)
    return "\n".join(lines)


def demo() -> str:
    """展示时间线，默认不展开失败案例。"""
    return render_timeline()


def render_failures() -> str:
    """单独展示每种范式的典型失败案例。"""
    return "\n".join(
        f"{stage.year} {stage.name}: {stage.failure_case}" for stage in STAGES
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="展示 Agent 技术时间线")
    mode.add_argument("--llm", action="store_true", help="请求模型总结发展脉络")
    mode.add_argument("--failures", action="store_true", help="展示各范式失败案例")
    mode.add_argument("--json", action="store_true", help="输出时间线 JSON")
    args = parser.parse_args()

    if args.llm:
        output = ask_llm(
            "比较符号主义、专家系统、搜索规划、概率模型、深度学习、强化学习、"
            "Transformer 和 LLM Agent，重点说明表示方式、反馈信号和主要限制。"
        )
    elif args.failures:
        output = render_failures()
    elif args.json:
        output = json.dumps(timeline_data(), ensure_ascii=False, indent=2)
    else:
        output = demo()
    print(output)


if __name__ == "__main__":
    main()

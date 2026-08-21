# Hello-Agents 深入实践

这是同一仓库中的第二条独立学习路线，参考 Datawhale 的 [Hello-Agents](https://github.com/datawhalechina/hello-agents) 项目。

当前仓库中的 [`achieve/`](../achieve/) 已经完成了 00～32 课。本项目不会导入 `achieve/` 的代码，而是按照 Hello-Agents 的原始章节重新实现；每个课程 README 会标记：

- ✅ 已学过：在 `achieve/` 中已有完整基础；
- 🔁 已学基础，继续深入：概念接触过，但本章有更完整内容；
- 🆕 未学习：当前没有系统覆盖；
- ⬆️ 进阶扩展：在已有知识之上的新实践。

## 目录

```text
hello-agents/
├── lessons/       # 按 Hello-Agents 章节组织的课程笔记
├── projects/      # 每章独立的实践项目
├── tests/         # 本路线的测试
├── CURRICULUM.md  # 原始章节课程表
├── COURSE_MAP.md  # 与 achieve 课程的知识映射
└── PROGRESS.md    # 学习进度
```

## 运行约定

```bash
cd /Users/yibo.chen/project/agents-learning/hello-agents
.venv311/bin/python projects/<project>/main.py
```

先完成课程 README，再创建对应代码；真实 LLM 配置使用本目录自己的 `.env`，不要提交 API Key。

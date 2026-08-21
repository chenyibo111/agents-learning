# AI Agent 学习工作区

这个仓库包含两条相互独立的学习路线：

| 项目 | 位置 | 定位 |
|---|---|---|
| achieve | [`achieve/`](achieve/) | 已完成的 00～32 课和研究助手工程 |
| hello-agents | [`hello-agents/`](hello-agents/) | 基于 Datawhale Hello-Agents 的深入实践路线 |

## achieve：已完成课程

- [课程表](achieve/CURRICULUM.md)
- [路线图](achieve/ROADMAP.md)
- [课程笔记](achieve/lessons/)
- [课程项目](achieve/projects/)
- [测试](achieve/tests/)

运行老项目时先进入 `achieve/`：

```bash
cd achieve
.venv311/bin/python projects/32-final-evaluation-deployment/main.py --demo --evaluate
```

## hello-agents：深入实践

这条路线不直接导入 `achieve/` 的代码，但会在课程 README 和 [`COURSE_MAP.md`](hello-agents/COURSE_MAP.md) 中标记已经学过的内容。

- [新课程表](hello-agents/CURRICULUM.md)
- [旧课程映射](hello-agents/COURSE_MAP.md)
- [学习进度](hello-agents/PROGRESS.md)
- [课程笔记](hello-agents/lessons/)
- [课程项目](hello-agents/projects/)

两个项目共用同一个 Git 仓库，但代码、课程进度和测试相互隔离。

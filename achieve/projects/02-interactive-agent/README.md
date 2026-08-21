# 02 - 交互式 Agent

这一课把第一课中的固定任务改成用户输入，并增加两个工具：

- `add_numbers`：加法
- `multiply_numbers`：乘法

## 运行

在学习工程根目录执行：

```powershell
python .\projects\02-interactive-agent\main.py
```

然后输入：

```text
请计算 12 乘以 8
```

## 本课目标

- 理解用户输入如何进入 `messages`；
- 观察模型如何在多个工具中选择；
- 观察不需要工具的问题如何直接回答；
- 理解工具名称、描述和参数 Schema 对模型决策的影响。

## 建议测试

```text
请计算 100 加 23
请计算 12 乘以 8
介绍一下北京
```


# Hello-Agents 测试

测试覆盖课程文件完整性、项目入口、共享循环和离线运行。真实 LLM 测试不默认执行，以免产生外部请求和费用。

从仓库根目录执行：

```bash
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v
```

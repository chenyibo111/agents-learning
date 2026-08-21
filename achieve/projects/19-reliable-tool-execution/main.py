import argparse
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Optional


class TransientToolError(RuntimeError):
    """工具遇到可以稍后重试的临时错误。"""


class ToolTimeoutError(TimeoutError):
    """工具执行超过允许的时间。"""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    max_attempts: int = 3
    base_delay: float = 1.0
    timeout_seconds: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (TransientToolError,)


def _matches_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return False


def validate_arguments(
    parameters: dict[str, Any], arguments: Any
) -> list[str]:
    if not isinstance(arguments, dict):
        return ["工具参数必须是 JSON 对象"]

    errors: list[str] = []
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    for name in required:
        if name not in arguments:
            errors.append(f"缺少必填参数：{name}")

    if parameters.get("additionalProperties") is False:
        for name in sorted(set(arguments) - set(properties)):
            errors.append(f"不允许的参数：{name}")

    for name, value in arguments.items():
        if name not in properties:
            continue
        expected_type = properties[name].get("type")
        if expected_type and not _matches_type(value, expected_type):
            errors.append(f"参数 {name} 必须是 {expected_type}")

    return errors


class ToolExecutor:
    def __init__(
        self,
        tools: dict[str, ToolSpec],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.tools = tools
        self.sleep = sleep
        self._idempotency_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def execute(
        self,
        tool_name: str,
        arguments: Any,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        spec = self.tools.get(tool_name)
        if spec is None:
            return self._failure(
                tool_name,
                "unknown_tool",
                f"未知工具：{tool_name}",
                attempts=0,
            )

        validation_errors = validate_arguments(spec.parameters, arguments)
        if validation_errors:
            return self._failure(
                tool_name,
                "validation_error",
                "；".join(validation_errors),
                attempts=0,
            )

        cache_key = (tool_name, idempotency_key) if idempotency_key else None
        if cache_key and cache_key in self._idempotency_cache:
            cached_result = dict(self._idempotency_cache[cache_key])
            cached_result["cached"] = True
            cached_result["attempts"] = 0
            return cached_result

        for attempt in range(1, spec.max_attempts + 1):
            try:
                result = self._run_with_timeout(spec, arguments)
                response = {
                    "ok": True,
                    "tool": tool_name,
                    "result": result,
                    "attempts": attempt,
                    "cached": False,
                }
                if cache_key:
                    self._idempotency_cache[cache_key] = dict(response)
                return response
            except ToolTimeoutError as error:
                return self._failure(
                    tool_name,
                    "timeout",
                    str(error),
                    attempts=attempt,
                )
            except Exception as error:
                if not isinstance(error, spec.retryable_exceptions):
                    return self._failure(
                        tool_name,
                        "tool_error",
                        str(error),
                        attempts=attempt,
                    )
                if attempt == spec.max_attempts:
                    return self._failure(
                        tool_name,
                        "retry_exhausted",
                        str(error),
                        attempts=attempt,
                    )

                delay = spec.base_delay * (2 ** (attempt - 1))
                print(
                    f"工具 {tool_name} 临时失败，{delay:g} 秒后重试 "
                    f"（第 {attempt}/{spec.max_attempts} 次尝试）"
                )
                self.sleep(delay)

        return self._failure(
            tool_name,
            "executor_error",
            "工具执行器异常结束",
            attempts=spec.max_attempts,
        )

    def _run_with_timeout(
        self,
        spec: ToolSpec,
        arguments: dict[str, Any],
    ) -> Any:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(spec.handler, arguments)
        try:
            return future.result(timeout=spec.timeout_seconds)
        except FutureTimeoutError as error:
            future.cancel()
            raise ToolTimeoutError(
                f"工具 {spec.name} 执行超过 {spec.timeout_seconds:g} 秒"
            ) from error
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _failure(
        tool_name: str,
        error_type: str,
        message: str,
        attempts: int,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "tool": tool_name,
            "error_type": error_type,
            "message": message,
            "attempts": attempts,
            "cached": False,
        }


class FlakyAdder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, arguments: dict[str, Any]) -> float:
        self.calls += 1
        if self.calls < 3:
            raise TransientToolError("模拟网络暂时不可用")
        return float(arguments["a"]) + float(arguments["b"])


def build_demo_executor() -> ToolExecutor:
    flaky_adder = FlakyAdder()
    records: list[str] = []

    def write_record(arguments: dict[str, Any]) -> str:
        records.append(str(arguments["value"]))
        return f"record-{len(records)}"

    tools = {
        "add_numbers": ToolSpec(
            name="add_numbers",
            description="计算两个数字的和",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
            handler=flaky_adder,
            max_attempts=3,
            base_delay=1.0,
        ),
        "slow_tool": ToolSpec(
            name="slow_tool",
            description="一个执行很慢的工具",
            parameters={"type": "object", "properties": {}},
            handler=lambda _: time.sleep(0.1),
            timeout_seconds=0.01,
        ),
        "write_record": ToolSpec(
            name="write_record",
            description="写入一条记录",
            parameters={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
                "additionalProperties": False,
            },
            handler=write_record,
        ),
    }
    return ToolExecutor(tools, sleep=lambda seconds: print(f"（演示跳过等待 {seconds:g} 秒）"))


def run_demo() -> None:
    executor = build_demo_executor()

    print("1. 参数校验：")
    print(executor.execute("add_numbers", {"a": "不是数字", "b": 2}))

    print("\n2. 临时错误重试：")
    print(executor.execute("add_numbers", {"a": 2, "b": 3}))

    print("\n3. 超时保护：")
    print(executor.execute("slow_tool", {}))

    print("\n4. 幂等键避免重复副作用：")
    first = executor.execute(
        "write_record", {"value": "hello"}, idempotency_key="request-1"
    )
    second = executor.execute(
        "write_record", {"value": "hello"}, idempotency_key="request-1"
    )
    print("第一次：", first)
    print("第二次：", second)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    if not args.demo:
        parser.error("本课目前提供离线演示，请使用 --demo")
    run_demo()


if __name__ == "__main__":
    main()

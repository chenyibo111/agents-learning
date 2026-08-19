"""Adapters for the lesson 29 research workflow."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


LESSON_29_DIR = Path(__file__).resolve().parents[1] / "29-research-task-workflow"


def lesson_29_modules() -> tuple[Any, Any, Any, Any, Any]:
    module_path = str(LESSON_29_DIR)
    if module_path not in sys.path:
        sys.path.insert(0, module_path)
    from retrieval_source import build_retriever
    from runtime import DemoRuntime, build_llm_runtime_from_env
    from workflow import require_langgraph, run_workflow

    return (
        build_retriever,
        DemoRuntime,
        build_llm_runtime_from_env,
        require_langgraph,
        run_workflow,
    )

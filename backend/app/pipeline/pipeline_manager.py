"""
Pipeline Manager — 流程编排器
参考 Claude Code 的 Workflow 系统:
pipeline() — 串行无屏障 (每完成一个阶段立即进入下一阶段)
parallel() — 并行有屏障 (所有 Agent 完成后汇总)
branch() — 条件分支 (根据结果动态路由)
"""
import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional

from ..models.schemas import ApprovalTask, ApprovalReport, PipelineStage


class PipelineManager:
    """
    审批流程编排器。

    参考 Claude Code Workflow patterns:
    - pipeline(): 串行链，item 完成即进入下一阶段
    - parallel(): 并行执行，所有完成后再汇总
    - branch(): 条件路由
    """

    def __init__(self):
        self.stages: List[PipelineStage] = []
        self._hooks: Dict[str, List[Callable]] = {
            "before_stage": [],
            "after_stage": [],
            "on_error": [],
        }

    def add_stage(self, stage: PipelineStage) -> "PipelineManager":
        """添加流水线阶段"""
        self.stages.append(stage)
        return self

    def hook(self, event: str, callback: Callable) -> "PipelineManager":
        """注册钩子 — 参考 Claude Code hooks 系统"""
        if event in self._hooks:
            self._hooks[event].append(callback)
        return self

    async def run(self, task: ApprovalTask,
                  stage_executor: Callable[[PipelineStage, ApprovalTask],
                                           Coroutine[Any, Any, Any]]
                  ) -> Dict[str, Any]:
        """
        串行执行所有阶段。
        返回每个阶段的结果 map。

        参考 Claude Code pipeline(items, stage1, stage2, ...)
        """
        results: Dict[str, Any] = {}
        context: Dict[str, Any] = {"task": task}

        for stage in self.stages:
            # 检查依赖
            for dep in stage.depends_on:
                if dep not in results:
                    raise ValueError(
                        f"Stage '{stage.name}' depends on '{dep}' which has not run"
                    )

            # before hook
            for hook_fn in self._hooks["before_stage"]:
                await hook_fn(stage, context)

            try:
                # 执行阶段
                result = await stage_executor(stage, task)
                results[stage.name] = result

                # after hook
                for hook_fn in self._hooks["after_stage"]:
                    await hook_fn(stage, result, context)

            except Exception as e:
                # error hook
                for hook_fn in self._hooks["on_error"]:
                    await hook_fn(stage, e, context)
                results[stage.name] = {"error": str(e)}

        return results

    @staticmethod
    async def parallel(executors: List[Callable[[], Coroutine[Any, Any, Any]]]
                       ) -> List[Any]:
        """
        并行执行多个任务，全部完成后返回。

        参考 Claude Code parallel(thunks): 屏障模式 —
        所有 thunk 完成后才返回，任一抛异常 → None。
        """
        async def safe_exec(fn):
            try:
                return await fn()
            except Exception:
                return None

        tasks = [safe_exec(fn) for fn in executors]
        return await asyncio.gather(*tasks)

    @staticmethod
    def branch(condition: Callable[[Dict[str, Any]], bool],
               true_branch: List[PipelineStage],
               false_branch: List[PipelineStage]) -> List[PipelineStage]:
        """
        条件分支 — 根据条件返回不同 stage 列表。

        参考 Claude Code 的条件逻辑（通过 plan 实现）。
        """
        return true_branch if condition else false_branch


async def build_default_pipeline() -> PipelineManager:
    """构建默认审批流水线"""
    pipeline = PipelineManager()

    pipeline.add_stage(PipelineStage(
        name="extract",
        agent_type="extract",
        tools=["extract_fields", "cross_validate"],
    ))
    pipeline.add_stage(PipelineStage(
        name="comply",
        agent_type="comply",
        tools=["search_law", "cite_clause"],
        depends_on=["extract"],
    ))
    pipeline.add_stage(PipelineStage(
        name="risk",
        agent_type="risk",
        tools=["risk_score", "suspend_node", "approve_node"],
        depends_on=["comply"],
    ))

    return pipeline

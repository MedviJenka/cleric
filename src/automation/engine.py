from collections.abc import Callable
from inspect import isawaitable
from typing import Any

from pydantic import BaseModel

from src.ai.agents.analyst.schemas import MonitoringSchema
from src.automation.failure_packet import format_failure_packet
from src.automation.runner import WorkflowRunResult
from src.automation.workflow import WorkflowDefinition


class SelfHealingRunResult(BaseModel):
    workflow_result: WorkflowRunResult
    analysis: MonitoringSchema | None = None
    repaired_workflow: WorkflowDefinition | None = None
    retry_result: WorkflowRunResult | None = None


class SelfHealingWorkflowEngine:
    """Runs deterministic workflows and invokes analyst repair only on failure."""

    def __init__(
        self,
        runner: Any,
        *,
        analyst: Callable[[str], Any],
        auto_apply_repairs: bool = False,
        min_auto_confidence: float = 0.75,
        repair_approval: Callable[[MonitoringSchema, WorkflowDefinition], Any] | None = None,
    ):
        self.runner = runner
        self.analyst = analyst
        self.auto_apply_repairs = auto_apply_repairs
        self.min_auto_confidence = min_auto_confidence
        self.repair_approval = repair_approval

    async def run_workflow(self, workflow: WorkflowDefinition) -> SelfHealingRunResult:
        workflow_result = await self._maybe_await(self.runner.run_workflow(workflow))
        if workflow_result.succeeded:
            return SelfHealingRunResult(workflow_result=workflow_result)

        failure_artifact = self._failure_artifact(workflow_result)
        if failure_artifact is None:
            return SelfHealingRunResult(workflow_result=workflow_result)

        packet = format_failure_packet(failure_artifact)
        analysis_result = await self._maybe_await(self.analyst(packet))
        analysis = MonitoringSchema.model_validate(analysis_result)
        if not await self._can_apply_repair(analysis, workflow):
            return SelfHealingRunResult(workflow_result=workflow_result, analysis=analysis)

        repaired_workflow = self._repaired_workflow(workflow, analysis)
        if repaired_workflow is None:
            return SelfHealingRunResult(workflow_result=workflow_result, analysis=analysis)

        retry_result = await self._maybe_await(self.runner.run_workflow(repaired_workflow))
        return SelfHealingRunResult(
            workflow_result=workflow_result,
            analysis=analysis,
            repaired_workflow=repaired_workflow,
            retry_result=retry_result,
        )

    @staticmethod
    def _failure_artifact(workflow_result: WorkflowRunResult):
        for step_result in workflow_result.step_results:
            if not step_result.succeeded and step_result.failure_artifact is not None:
                return step_result.failure_artifact
        return None

    async def _can_apply_repair(self, analysis: MonitoringSchema, workflow: WorkflowDefinition) -> bool:
        if not self.auto_apply_repairs or not analysis.fix_needed:
            return False
        if analysis.confidence_level < self.min_auto_confidence:
            return False
        if analysis.requires_human_approval:
            if self.repair_approval is None:
                return False
            return bool(await self._maybe_await(self.repair_approval(analysis, workflow)))
        return analysis.risk_level == "low"

    @staticmethod
    def _repaired_workflow(workflow: WorkflowDefinition, analysis: MonitoringSchema) -> WorkflowDefinition | None:
        patch = analysis.what_to_fix
        step_id = patch.get("step_id")
        if not isinstance(step_id, str):
            return None

        workflow_data = workflow.model_dump()
        repaired = False
        for step in workflow_data["steps"]:
            if step["id"] != step_id:
                continue
            for field in ("action", "target", "value", "expected_outcome"):
                if field in patch:
                    step[field] = patch[field]
                    repaired = True
            break
        if not repaired:
            return None
        return WorkflowDefinition.model_validate(workflow_data)

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if isawaitable(value):
            return await value
        return value

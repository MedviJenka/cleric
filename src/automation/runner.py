from datetime import UTC, datetime
from inspect import isawaitable
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from src.automation.workflow import WorkflowDefinition, WorkflowStep


class FailureArtifact(BaseModel):
    workflow_id: str | None = Field(default=None, description="Workflow id when running a full workflow")
    run_id: str = Field(..., description="Unique run identifier for artifact correlation")
    failed_step_id: str = Field(..., description="Workflow step that failed")
    failed_step_intent: str = Field(..., description="Business intent of the failed step")
    current_url: str | None = Field(default=None, description="Current browser URL at failure time")
    screenshot_path: str = Field(..., description="Captured screenshot path")
    dom_snapshot_path: str = Field(..., description="Captured DOM snapshot path")
    expected_outcome: str = Field(..., description="Business outcome the step was expected to produce")
    risk: str = Field(..., description="Business risk category carried by the failed step")
    error: str = Field(..., description="Last deterministic runner error")


class StepResult(BaseModel):
    succeeded: bool
    step_id: str
    attempted_targets: list[str] = Field(default_factory=list)
    failure_artifact: FailureArtifact | None = None


class WorkflowRunResult(BaseModel):
    succeeded: bool
    workflow_id: str
    step_results: list[StepResult] = Field(default_factory=list)
    failed_step_id: str | None = None


class PlaywrightWorkflowRunner:
    """Deterministic Playwright-compatible workflow runner.

    The runner accepts a Playwright Page or a test double with the same methods.
    It owns execution and artifact capture; AI repair logic stays outside this path.
    """

    def __init__(
        self,
        page: Any,
        *,
        artifact_dir: Path | str = Path("artifacts/workflow-runs"),
        run_id: str | None = None,
        verifier: Callable[[Any, WorkflowStep], Any] | None = None,
    ):
        self.page = page
        self.artifact_dir = Path(artifact_dir)
        self.run_id = run_id or self._new_run_id()
        self.verifier = verifier


    async def run_workflow(self, workflow: WorkflowDefinition) -> WorkflowRunResult:
        step_results: list[StepResult] = []
        for step in workflow.steps:
            result = await self.run_step(step, workflow_id=workflow.id)
            step_results.append(result)
            if not result.succeeded:
                return WorkflowRunResult(
                    succeeded=False,
                    workflow_id=workflow.id,
                    step_results=step_results,
                    failed_step_id=step.id,
                )
        return WorkflowRunResult(succeeded=True, workflow_id=workflow.id, step_results=step_results)

    async def run_step(self, step: WorkflowStep, *, workflow_id: str | None = None) -> StepResult:
        if step.action == "click":
            return await self._click(step, workflow_id=workflow_id)
        if step.action == "fill":
            return await self._fill(step, workflow_id=workflow_id)
        raise ValueError(f"unsupported workflow action: {step.action}")

    async def _click(self, step: WorkflowStep, *, workflow_id: str | None) -> StepResult:
        attempted_targets: list[str] = []
        last_error: Exception | None = None
        for candidate_name in step.target.candidate_names():
            attempted_targets.append(candidate_name)
            try:
                locator = self.page.get_by_role(step.target.role, name=candidate_name)
                await self._maybe_await(locator.click())
            except Exception as exc:  # deterministic miss; try the next semantic fallback
                last_error = exc
                continue

            verified = await self._verify_step(step)
            if not verified:
                artifact = await self._capture_failure_artifact(
                    step,
                    workflow_id=workflow_id,
                    error=f"Expected outcome was not verified: {step.expected_outcome}",
                )
                return StepResult(
                    succeeded=False,
                    step_id=step.id,
                    attempted_targets=attempted_targets,
                    failure_artifact=artifact,
                )
            return StepResult(succeeded=True, step_id=step.id, attempted_targets=attempted_targets)
        artifact = await self._capture_failure_artifact(
            step,
            workflow_id=workflow_id,
            error=str(last_error) if last_error else "No target candidates were available.",
        )
        return StepResult(
            succeeded=False,
            step_id=step.id,
            attempted_targets=attempted_targets,
            failure_artifact=artifact,
        )

    async def _fill(self, step: WorkflowStep, *, workflow_id: str | None) -> StepResult:
        attempted_targets: list[str] = []
        last_error: Exception | None = None
        for candidate_name in step.target.candidate_names():
            attempted_targets.append(candidate_name)
            try:
                locator = self.page.get_by_role(step.target.role, name=candidate_name)
                await self._maybe_await(locator.fill(step.value or ""))
            except Exception as exc:  # deterministic miss; try the next semantic fallback
                last_error = exc
                continue

            verified = await self._verify_step(step)
            if not verified:
                artifact = await self._capture_failure_artifact(
                    step,
                    workflow_id=workflow_id,
                    error=f"Expected outcome was not verified: {step.expected_outcome}",
                )
                return StepResult(
                    succeeded=False,
                    step_id=step.id,
                    attempted_targets=attempted_targets,
                    failure_artifact=artifact,
                )
            return StepResult(succeeded=True, step_id=step.id, attempted_targets=attempted_targets)
        artifact = await self._capture_failure_artifact(
            step,
            workflow_id=workflow_id,
            error=str(last_error) if last_error else "No target candidates were available.",
        )
        return StepResult(
            succeeded=False,
            step_id=step.id,
            attempted_targets=attempted_targets,
            failure_artifact=artifact,
        )

    async def _capture_failure_artifact(self, step: WorkflowStep, *, workflow_id: str | None, error: str) -> FailureArtifact:
        step_dir = self.artifact_dir / self.run_id / step.id
        step_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = step_dir / "screenshot.png"
        dom_snapshot_path = step_dir / "dom.html"

        await self._capture_screenshot(screenshot_path)
        dom_snapshot_path.write_text(await self._capture_dom(), encoding="utf-8")

        return FailureArtifact(
            workflow_id=workflow_id,
            run_id=self.run_id,
            failed_step_id=step.id,
            failed_step_intent=step.intent,
            current_url=getattr(self.page, "url", None),
            screenshot_path=str(screenshot_path),
            dom_snapshot_path=str(dom_snapshot_path),
            expected_outcome=step.expected_outcome,
            risk=step.risk,
            error=error,
        )

    async def _verify_step(self, step: WorkflowStep) -> bool:
        if self.verifier is None:
            return True
        return bool(await self._maybe_await(self.verifier(self.page, step)))

    async def _capture_screenshot(self, screenshot_path: Path) -> None:
        screenshot = getattr(self.page, "screenshot", None)
        if screenshot is None:
            screenshot_path.write_bytes(b"")
            return
        await self._maybe_await(screenshot(path=str(screenshot_path), full_page=True))

    async def _capture_dom(self) -> str:
        content = getattr(self.page, "content", None)
        if content is None:
            return ""
        return await self._maybe_await(content())

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if isawaitable(value):
            return await value
        return value

    @staticmethod
    def _new_run_id() -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{timestamp}-{uuid4().hex[:8]}"

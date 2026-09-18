import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.automation.engine import SelfHealingWorkflowEngine
from src.automation.failure_packet import format_failure_packet
from src.automation.runner import FailureArtifact, StepResult, WorkflowRunResult
from src.automation.workflow import WorkflowDefinition


def run(coro):
    return asyncio.run(coro)


class FakeRunner:
    def __init__(self, result: WorkflowRunResult):
        self.result = result
        self.workflow_ids: list[str] = []

    async def run_workflow(self, workflow: WorkflowDefinition) -> WorkflowRunResult:
        self.workflow_ids.append(workflow.id)
        return self.result


class SequenceRunner:
    def __init__(self, results: list[WorkflowRunResult]):
        self.results = list(results)
        self.workflows: list[WorkflowDefinition] = []

    async def run_workflow(self, workflow: WorkflowDefinition) -> WorkflowRunResult:
        self.workflows.append(workflow)
        return self.results.pop(0)


def food_checkout_workflow() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate(
        {
            "id": "food_delivery_checkout",
            "steps": [
                {
                    "id": "place_food_order",
                    "intent": "Place the food order",
                    "action": "click",
                    "target": {"role": "button", "name": "Place order"},
                    "risk": "financial_submission",
                    "expected_outcome": "order is submitted",
                }
            ],
        }
    )


class TestFailurePacket(unittest.TestCase):
    def test_failure_packet_contains_runner_artifacts_for_analyst(self):
        with TemporaryDirectory() as artifact_dir:
            dom_path = Path(artifact_dir) / "dom.html"
            dom_path.write_text('<button type="button" disabled>Place order</button>', encoding="utf-8")
            screenshot_path = Path(artifact_dir) / "screenshot.png"
            screenshot_path.write_bytes(b"fake screenshot")
            artifact = FailureArtifact(
                workflow_id="food_delivery_checkout",
                run_id="run-1",
                failed_step_id="place_food_order",
                failed_step_intent="Place the food order",
                current_url="http://localhost:3000",
                screenshot_path=str(screenshot_path),
                dom_snapshot_path=str(dom_path),
                expected_outcome="order is submitted",
                risk="financial_submission",
                error="Expected outcome was not verified: order is submitted",
            )

            packet = format_failure_packet(artifact)

        self.assertIn("workflow_id=food_delivery_checkout", packet)
        self.assertIn("failed_step_id=place_food_order", packet)
        self.assertIn("expected_outcome=order is submitted", packet)
        self.assertIn("risk=financial_submission", packet)
        self.assertIn("Place order", packet)
        self.assertIn("screenshot_path=", packet)


class TestSelfHealingWorkflowEngine(unittest.TestCase):
    def test_engine_calls_analyst_only_after_runner_failure(self):
        with TemporaryDirectory() as artifact_dir:
            dom_path = Path(artifact_dir) / "dom.html"
            dom_path.write_text('<button type="button" disabled>Place order</button>', encoding="utf-8")
            screenshot_path = Path(artifact_dir) / "screenshot.png"
            screenshot_path.write_bytes(b"fake screenshot")
            artifact = FailureArtifact(
                workflow_id="food_delivery_checkout",
                run_id="run-1",
                failed_step_id="place_food_order",
                failed_step_intent="Place the food order",
                current_url="http://localhost:3000",
                screenshot_path=str(screenshot_path),
                dom_snapshot_path=str(dom_path),
                expected_outcome="order is submitted",
                risk="financial_submission",
                error="Expected outcome was not verified: order is submitted",
            )
            runner_result = WorkflowRunResult(
                succeeded=False,
                workflow_id="food_delivery_checkout",
                step_results=[StepResult(succeeded=False, step_id="place_food_order", failure_artifact=artifact)],
                failed_step_id="place_food_order",
            )
            received_packets: list[str] = []

            def analyst(packet: str) -> dict:
                received_packets.append(packet)
                return {
                    "fix_needed": True,
                    "failure_class": "validation_changed",
                    "what_changed": "Checkout stayed disabled instead of submitting the order.",
                    "what_to_fix": {"step_id": "place_food_order"},
                    "suggested_repair": [
                        {
                            "action": "fill",
                            "target": "Delivery address",
                            "rationale": "The food app requires a delivery address before checkout is enabled.",
                        }
                    ],
                    "confidence_level": 0.82,
                    "risk_level": "high",
                    "requires_human_approval": True,
                    "escalation_summary": "Food order submission is financial and requires approval.",
                    "evidence": ["Place order is disabled"],
                }

            result = run(SelfHealingWorkflowEngine(FakeRunner(runner_result), analyst=analyst).run_workflow(food_checkout_workflow()))

        self.assertFalse(result.workflow_result.succeeded)
        self.assertEqual(len(received_packets), 1)
        self.assertIn("failed_step_id=place_food_order", received_packets[0])
        self.assertTrue(result.analysis.requires_human_approval)

    def test_engine_auto_applies_safe_workflow_repair_and_retries(self):
        with TemporaryDirectory() as artifact_dir:
            dom_path = Path(artifact_dir) / "dom.html"
            dom_path.write_text('<button type="button">Review order</button>', encoding="utf-8")
            screenshot_path = Path(artifact_dir) / "screenshot.png"
            screenshot_path.write_bytes(b"fake screenshot")
            artifact = FailureArtifact(
                workflow_id="food_delivery_checkout",
                run_id="run-1",
                failed_step_id="place_food_order",
                failed_step_intent="Place the food order",
                current_url="http://localhost:3000",
                screenshot_path=str(screenshot_path),
                dom_snapshot_path=str(dom_path),
                expected_outcome="order is submitted",
                risk="read_only",
                error="missing semantic target ('button', 'Place order')",
            )
            failed_result = WorkflowRunResult(
                succeeded=False,
                workflow_id="food_delivery_checkout",
                step_results=[StepResult(succeeded=False, step_id="place_food_order", failure_artifact=artifact)],
                failed_step_id="place_food_order",
            )
            repaired_result = WorkflowRunResult(
                succeeded=True,
                workflow_id="food_delivery_checkout",
                step_results=[StepResult(succeeded=True, step_id="place_food_order")],
            )
            runner = SequenceRunner([failed_result, repaired_result])

            def analyst(packet: str) -> dict:
                return {
                    "fix_needed": True,
                    "failure_class": "text_changed",
                    "what_changed": "Checkout button text changed from Place order to Review order.",
                    "what_to_fix": {
                        "step_id": "place_food_order",
                        "target": {"role": "button", "name": "Review order"},
                    },
                    "suggested_repair": [
                        {
                            "action": "click",
                            "target": "button: Review order",
                            "rationale": "The renamed button preserves the original submit intent.",
                        }
                    ],
                    "confidence_level": 0.91,
                    "risk_level": "low",
                    "requires_human_approval": False,
                    "escalation_summary": "Safe workflow target rename can be retried automatically.",
                    "evidence": ["DOM contains Review order"],
                }

            original_workflow = food_checkout_workflow()
            result = run(
                SelfHealingWorkflowEngine(runner, analyst=analyst, auto_apply_repairs=True).run_workflow(
                    original_workflow
                )
            )

        self.assertFalse(result.workflow_result.succeeded)
        self.assertTrue(result.retry_result.succeeded)
        self.assertEqual(len(runner.workflows), 2)
        self.assertEqual(runner.workflows[0].steps[0].target.name, "Place order")
        self.assertEqual(runner.workflows[1].steps[0].target.name, "Review order")
        self.assertEqual(result.repaired_workflow.steps[0].target.name, "Review order")
        self.assertEqual(original_workflow.steps[0].target.name, "Place order")

    def test_engine_does_not_auto_apply_high_risk_repair_without_approval(self):
        with TemporaryDirectory() as artifact_dir:
            dom_path = Path(artifact_dir) / "dom.html"
            dom_path.write_text('<button type="button">Review order</button>', encoding="utf-8")
            screenshot_path = Path(artifact_dir) / "screenshot.png"
            screenshot_path.write_bytes(b"fake screenshot")
            artifact = FailureArtifact(
                workflow_id="food_delivery_checkout",
                run_id="run-1",
                failed_step_id="place_food_order",
                failed_step_intent="Place the food order",
                current_url="http://localhost:3000",
                screenshot_path=str(screenshot_path),
                dom_snapshot_path=str(dom_path),
                expected_outcome="order is submitted",
                risk="financial_submission",
                error="missing semantic target ('button', 'Place order')",
            )
            failed_result = WorkflowRunResult(
                succeeded=False,
                workflow_id="food_delivery_checkout",
                step_results=[StepResult(succeeded=False, step_id="place_food_order", failure_artifact=artifact)],
                failed_step_id="place_food_order",
            )
            runner = SequenceRunner([failed_result])

            def analyst(packet: str) -> dict:
                return {
                    "fix_needed": True,
                    "failure_class": "text_changed",
                    "what_changed": "Checkout button text changed from Place order to Review order.",
                    "what_to_fix": {
                        "step_id": "place_food_order",
                        "target": {"role": "button", "name": "Review order"},
                    },
                    "suggested_repair": [
                        {
                            "action": "click",
                            "target": "button: Review order",
                            "rationale": "The renamed button preserves the original submit intent.",
                        }
                    ],
                    "confidence_level": 0.91,
                    "risk_level": "high",
                    "requires_human_approval": True,
                    "escalation_summary": "Financial submit repair needs approval.",
                    "evidence": ["DOM contains Review order"],
                }

            result = run(
                SelfHealingWorkflowEngine(runner, analyst=analyst, auto_apply_repairs=True).run_workflow(
                    food_checkout_workflow()
                )
            )

        self.assertFalse(result.workflow_result.succeeded)
        self.assertIsNone(result.retry_result)
        self.assertIsNone(result.repaired_workflow)
        self.assertEqual(len(runner.workflows), 1)

    def test_engine_does_not_call_analyst_after_successful_runner_result(self):
        runner_result = WorkflowRunResult(
            succeeded=True,
            workflow_id="food_delivery_checkout",
            step_results=[StepResult(succeeded=True, step_id="place_food_order")],
        )

        def analyst(packet: str) -> dict:
            raise AssertionError("analyst must not run on deterministic success")

        result = run(SelfHealingWorkflowEngine(FakeRunner(runner_result), analyst=analyst).run_workflow(food_checkout_workflow()))

        self.assertTrue(result.workflow_result.succeeded)
        self.assertIsNone(result.analysis)


if __name__ == "__main__":
    unittest.main()

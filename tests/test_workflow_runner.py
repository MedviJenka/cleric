import asyncio
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError
import pytest

from src.automation.runner import PlaywrightWorkflowRunner
from src.automation.workflow import WorkflowDefinition, WorkflowStep


class FakeLocator:

    def __init__(
        self,
        role: str,
        name: str,
        available_targets: set[tuple[str, str]],
        clicked: list[tuple[str, str]],
        filled: dict[tuple[str, str], str],
    ):
        self.role = role
        self.name = name
        self.available_targets = available_targets
        self.clicked = clicked
        self.filled = filled

    async def click(self):
        target = (self.role, self.name)
        if target not in self.available_targets:
            raise RuntimeError(f"missing target {self.role}[name={self.name!r}]")
        self.clicked.append(target)

    async def fill(self, value: str):
        target = (self.role, self.name)
        if target not in self.available_targets:
            raise RuntimeError(f"missing target {self.role}[name={self.name!r}]")
        self.filled[target] = value


class FakePage:
    url = "https://example.test/invoices/1042"

    def __init__(self, available_targets: set[tuple[str, str]]):
        self.available_targets = available_targets
        self.clicked: list[tuple[str, str]] = []
        self.filled: dict[tuple[str, str], str] = {}

    def get_by_role(self, role: str, *, name: str):
        return FakeLocator(role, name, self.available_targets, self.clicked, self.filled)

    async def screenshot(self, *, path: str, full_page: bool):
        Path(path).write_bytes(b"fake screenshot")

    async def content(self):
        return "<button>Send for Approval</button>"


def run(coro):
    return asyncio.run(coro)


class TestWorkflowDefinition(unittest.TestCase):
    def test_workflow_step_preserves_business_intent_and_target_fallbacks(self):
        step = WorkflowStep.model_validate(
            {
                "id": "submit_invoice_for_approval",
                "intent": "Submit the invoice for approval",
                "action": "click",
                "target": {
                    "role": "button",
                    "name": "Submit Invoice",
                    "fallback_text": ["Send for Approval", "Submit for Approval"],
                },
                "risk": "financial_submission",
                "expected_outcome": "invoice status becomes Pending Approval",
            }
        )

        self.assertEqual(step.target.fallback_text, ["Send for Approval", "Submit for Approval"])
        self.assertEqual(step.risk, "financial_submission")

    def test_workflow_definition_rejects_duplicate_step_ids(self):
        step = {
            "id": "submit_invoice_for_approval",
            "intent": "Submit the invoice for approval",
            "action": "click",
            "target": {"role": "button", "name": "Submit Invoice"},
            "risk": "financial_submission",
            "expected_outcome": "invoice status becomes Pending Approval",
        }

        with self.assertRaises(ValidationError):
            WorkflowDefinition.model_validate({"id": "invoice_approval", "steps": [step, step]})

    def test_fill_workflow_steps_require_values(self):
        with pytest.raises(ValidationError, match="fill workflow steps require a value"):
            WorkflowStep.model_validate(
                {
                    "id": "enter_delivery_address",
                    "intent": "Enter the delivery address",
                    "action": "fill",
                    "target": {"role": "textbox", "name": "Delivery address"},
                    "risk": "none",
                    "expected_outcome": "checkout is unlocked",
                }
            )


class TestPlaywrightWorkflowRunner(unittest.TestCase):
    def test_runner_clicks_first_matching_semantic_target_including_fallbacks(self):
        page = FakePage({("button", "Send for Approval")})
        step = WorkflowStep.model_validate(
            {
                "id": "submit_invoice_for_approval",
                "intent": "Submit the invoice for approval",
                "action": "click",
                "target": {
                    "role": "button",
                    "name": "Submit Invoice",
                    "fallback_text": ["Send for Approval"],
                },
                "risk": "financial_submission",
                "expected_outcome": "invoice status becomes Pending Approval",
            }
        )

        with TemporaryDirectory() as artifact_dir:
            result = run(PlaywrightWorkflowRunner(page, artifact_dir=Path(artifact_dir)).run_step(step))

        self.assertTrue(result.succeeded)
        self.assertEqual(page.clicked, [("button", "Send for Approval")])
        self.assertIsNone(result.failure_artifact)

    def test_runner_executes_food_app_checkout_workflow_actions(self):
        page = FakePage(
            {
                ("button", "Add Pesto Panini"),
                ("textbox", "Delivery address"),
                ("button", "Place order"),
            }
        )
        workflow = WorkflowDefinition.model_validate(
            {
                "id": "food_delivery_checkout",
                "steps": [
                    {
                        "id": "add_pesto_panini",
                        "intent": "Add Pesto Panini to the cart",
                        "action": "click",
                        "target": {"role": "button", "name": "Add Pesto Panini"},
                        "risk": "none",
                        "expected_outcome": "cart contains Pesto Panini",
                    },
                    {
                        "id": "enter_delivery_address",
                        "intent": "Enter the delivery address",
                        "action": "fill",
                        "target": {"role": "textbox", "name": "Delivery address"},
                        "value": "123 Market Street",
                        "risk": "none",
                        "expected_outcome": "checkout is unlocked",
                    },
                    {
                        "id": "place_food_order",
                        "intent": "Place the food order",
                        "action": "click",
                        "target": {"role": "button", "name": "Place order"},
                        "risk": "financial_submission",
                        "expected_outcome": "order is submitted",
                    },
                ],
            }
        )

        with TemporaryDirectory() as artifact_dir:
            result = run(PlaywrightWorkflowRunner(page, artifact_dir=Path(artifact_dir)).run_workflow(workflow))

        self.assertTrue(result.succeeded)
        self.assertEqual(page.clicked, [("button", "Add Pesto Panini"), ("button", "Place order")])
        self.assertEqual(page.filled[("textbox", "Delivery address")], "123 Market Street")

    def test_runner_treats_unverified_business_outcome_as_failure(self):
        page = FakePage({("button", "Submit Invoice")})
        verified_steps: list[str] = []

        async def verifier(page, step):
            verified_steps.append(step.id)
            return False

        step = WorkflowStep.model_validate(
            {
                "id": "submit_invoice_for_approval",
                "intent": "Submit the invoice for approval",
                "action": "click",
                "target": {"role": "button", "name": "Submit Invoice"},
                "risk": "financial_submission",
                "expected_outcome": "invoice status becomes Pending Approval",
            }
        )

        with TemporaryDirectory() as artifact_dir:
            result = run(PlaywrightWorkflowRunner(page, artifact_dir=Path(artifact_dir), verifier=verifier).run_step(step))

            self.assertFalse(result.succeeded)
            self.assertEqual(verified_steps, ["submit_invoice_for_approval"])
            self.assertIn("Expected outcome was not verified", result.failure_artifact.error)
            self.assertTrue(Path(result.failure_artifact.screenshot_path).exists())

    def test_runner_returns_failure_artifact_when_no_target_matches(self):
        page = FakePage(set())
        step = WorkflowStep.model_validate(
            {
                "id": "submit_invoice_for_approval",
                "intent": "Submit the invoice for approval",
                "action": "click",
                "target": {
                    "role": "button",
                    "name": "Submit Invoice",
                    "fallback_text": ["Send for Approval"],
                },
                "risk": "financial_submission",
                "expected_outcome": "invoice status becomes Pending Approval",
            }
        )

        with TemporaryDirectory() as artifact_dir:
            result = run(PlaywrightWorkflowRunner(page, artifact_dir=Path(artifact_dir)).run_step(step))

            self.assertFalse(result.succeeded)
            self.assertEqual(result.failure_artifact.failed_step_id, "submit_invoice_for_approval")
            self.assertEqual(result.failure_artifact.failed_step_intent, "Submit the invoice for approval")
            self.assertEqual(result.failure_artifact.current_url, "https://example.test/invoices/1042")
            self.assertTrue(Path(result.failure_artifact.screenshot_path).exists())
            self.assertIn("Send for Approval", Path(result.failure_artifact.dom_snapshot_path).read_text(encoding="utf-8"))

    def test_runner_stops_workflow_at_first_failed_step(self):
        page = FakePage({("button", "Open Invoice")})
        workflow = WorkflowDefinition.model_validate(
            {
                "id": "invoice_approval",
                "steps": [
                    {
                        "id": "open_invoice",
                        "intent": "Open the invoice",
                        "action": "click",
                        "target": {"role": "button", "name": "Open Invoice"},
                        "risk": "navigation",
                        "expected_outcome": "invoice detail page is visible",
                    },
                    {
                        "id": "submit_invoice_for_approval",
                        "intent": "Submit the invoice for approval",
                        "action": "click",
                        "target": {"role": "button", "name": "Submit Invoice"},
                        "risk": "financial_submission",
                        "expected_outcome": "invoice status becomes Pending Approval",
                    },
                ],
            }
        )

        with TemporaryDirectory() as artifact_dir:
            result = run(PlaywrightWorkflowRunner(page, artifact_dir=Path(artifact_dir)).run_workflow(workflow))

        self.assertFalse(result.succeeded)
        self.assertEqual([step.step_id for step in result.step_results], ["open_invoice", "submit_invoice_for_approval"])
        self.assertEqual(result.failed_step_id, "submit_invoice_for_approval")
        self.assertEqual(result.step_results[-1].failure_artifact.workflow_id, "invoice_approval")


if __name__ == "__main__":
    unittest.main()

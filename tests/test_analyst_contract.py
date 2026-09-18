import os
import unittest
from pathlib import Path

os.environ.setdefault("APP_VERSION", "test")
os.environ.setdefault("AGENT_VERBOSE", "false")
os.environ.setdefault("CREWAI_TOOLS_ALLOW_UNSAFE_PATHS", "false")
os.environ.setdefault("GHCR_TOKEN", "test-token")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_MODEL", "openai/gpt-5.5")

from pydantic import ValidationError

from src.ai.agents.analyst.crew import AnalystAgent, analyst_agent
from src.ai.agents.analyst.schemas import MonitoringSchema, RepairAction

DUMMY_LOG_PATH = Path(__file__).with_name("fixtures") / "dummy_automation_failure.log"


def load_dummy_log() -> str:
    return DUMMY_LOG_PATH.read_text(encoding="utf-8")


class TestAnalystContract(unittest.TestCase):

    def test_agent_can_be_constructed_without_required_dataclass_arguments(self):
        analyst = AnalystAgent()
        crew = analyst.crew()

        self.assertEqual(len(crew.agents), 4)
        self.assertEqual(len(crew.tasks), 4)

    def test_dummy_ai_log_contains_selector_change_and_risk_evidence(self):
        dummy_log = load_dummy_log()

        self.assertIn("failed_step_id=submit_invoice_for_approval", dummy_log)
        self.assertIn("role=button[name=\"Submit Invoice\"]", dummy_log)
        self.assertIn("menuitem \"Send for Approval\"", dummy_log)
        self.assertIn("financial data", dummy_log)

    @unittest.skipUnless(os.getenv("RUN_AI_TESTS") == "1", "set RUN_AI_TESTS=1 to run the live CrewAI analyst test")
    def test_live_ai_analyst_processes_dummy_failure_log(self):
        result = analyst_agent(load_dummy_log())
        schema = MonitoringSchema.model_validate(result)

        self.assertTrue(schema.fix_needed)
        self.assertIn(schema.failure_class, {"selector_changed", "text_changed", "layout_changed", "flow_changed"})
        self.assertTrue(schema.requires_human_approval)

    def test_final_monitoring_schema_rejects_confidence_outside_probability_range(self):
        with self.assertRaises(ValidationError):
            MonitoringSchema(
                fix_needed=True,
                failure_class="selector_changed",
                what_changed="Button label changed.",
                suggested_repair=[RepairAction(action="click", target="Send for Approval", rationale="Same business intent.")],
                confidence_level=1.2,
                risk_level="low",
                requires_human_approval=False,
                escalation_summary="Repair can be retried safely.",
                evidence=["Observed replacement approval control."],
            )

    def test_high_risk_repairs_require_human_approval(self):
        with self.assertRaises(ValidationError):
            MonitoringSchema(
                fix_needed=True,
                failure_class="flow_changed",
                what_changed="Approval action moved into a menu.",
                suggested_repair=[RepairAction(action="click", target="More Actions > Send for Approval", rationale="Matches approval intent.")],
                confidence_level=0.82,
                risk_level="high",
                requires_human_approval=False,
                escalation_summary="Financial workflow requires approval.",
                evidence=["Action submits financial data."],
            )


if __name__ == "__main__":
    unittest.main()

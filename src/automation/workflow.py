from typing import Literal

from pydantic import BaseModel, Field, model_validator

WorkflowAction = Literal["click", "fill"]
BusinessRisk = Literal[
    "none",
    "read_only",
    "navigation",
    "financial_submission",
    "money_movement",
    "data_deletion",
    "permission_change",
    "credential_entry",
    "mfa",
    "external_send",
    "legal_or_compliance",
]


class WorkflowTarget(BaseModel):
    role: str = Field(..., min_length=1, description="ARIA role used by the deterministic runner")
    name: str = Field(..., min_length=1, description="Primary accessible name for the target control")
    fallback_text: list[str] = Field(default_factory=list, description="Alternate accessible names for the same intent")

    def candidate_names(self) -> list[str]:
        names = [self.name]
        names.extend(name for name in self.fallback_text if name not in names)
        return names


class WorkflowStep(BaseModel):
    id: str = Field(..., min_length=1, description="Stable workflow step identifier")
    intent: str = Field(..., min_length=1, description="Business intent the step is meant to accomplish")
    action: WorkflowAction = Field(..., description="Deterministic action to execute")
    target: WorkflowTarget = Field(..., description="Semantic target for the action")
    risk: BusinessRisk = Field(..., description="Business risk category for policy decisions")
    expected_outcome: str = Field(..., min_length=1, description="Observable business outcome to verify after execution")
    value: str | None = Field(default=None, description="Input value for fill actions")

    @model_validator(mode="after")
    def require_value_for_fill_actions(self) -> "WorkflowStep":
        if self.action == "fill" and self.value is None:
            raise ValueError("fill workflow steps require a value")
        return self


class WorkflowDefinition(BaseModel):
    id: str = Field(..., min_length=1, description="Stable workflow identifier")
    steps: list[WorkflowStep] = Field(..., min_length=1, description="Ordered deterministic workflow steps")

    @model_validator(mode="after")
    def require_unique_step_ids(self) -> "WorkflowDefinition":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for step in self.steps:
            if step.id in seen:
                duplicates.add(step.id)
            seen.add(step.id)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise ValueError(f"workflow step ids must be unique: {duplicate_list}")
        return self

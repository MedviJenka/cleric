from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


FailureClass = Literal[
    'none',
    'selector_changed',
    'text_changed',
    'layout_changed',
    'flow_changed',
    'authentication_expired',
    'permission_changed',
    'network_failure',
    'validation_changed',
    'app_bug',
    'automation_bug',
    'unknown',
]


RiskLevel = Literal['low', 'medium', 'high', 'critical']


class RepairAction(BaseModel):
    action:    str = Field(..., description='Executable repair action, for example click or wait_for')
    target:    str = Field(..., description='Semantic target for the repair action')
    rationale: str = Field(..., description='Why this action satisfies the original step intent')


class MonitoringSchema(BaseModel):

    fix_needed:              bool               = Field(..., description='Whether the automation needs a workflow repair')
    failure_class:           FailureClass       = Field(..., description='Most likely class of automation failure')
    what_changed:            str                = Field(..., description='Observed app or workflow change that caused the failure')
    what_to_fix:             dict[str, Any]     = Field(default_factory=dict, description='Patch-ready fields to update in the workflow definition')
    suggested_repair:        list[RepairAction] = Field(default_factory=list, description='Ordered repair actions to try or approve')
    confidence_level:        float              = Field(..., ge=0, le=1,  description='Probability that the diagnosis and repair are correct')
    risk_level:              RiskLevel          = Field(..., description='Business risk of applying the repair')
    requires_human_approval: bool               = Field(..., description='Whether a human must approve before retrying')
    escalation_summary:      str                = Field(..., description='Short operator-facing explanation with evidence and next step')
    evidence:                list[str]          = Field(default_factory=list, description='Specific observations supporting the diagnosis')

    @model_validator(mode='after')
    def require_approval_for_high_risk_repairs(self) -> 'MonitoringSchema':
        if self.risk_level in {'high', 'critical'} and not self.requires_human_approval:
            raise ValueError('high and critical risk repairs require human approval')
        return self

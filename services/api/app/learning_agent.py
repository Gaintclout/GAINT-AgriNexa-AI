"""Human-supervised, stateless feedback analysis.

No model training, database writes, external calls, or deployment.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentDomain(str, Enum):
    weather = "weather"
    crop_advisory = "crop_advisory"
    market = "market"
    schemes = "schemes"
    escalation = "escalation"


class FeedbackOutcome(str, Enum):
    helpful = "helpful"
    inaccurate = "inaccurate"
    incomplete = "incomplete"
    outdated = "outdated"
    unsafe = "unsafe"


class FeedbackEvidence(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    description: str = Field(min_length=10, max_length=1000)
    source_type: Literal[
        "field_observation",
        "official_source",
        "expert_review",
        "farmer_report",
        "other",
    ]
    source_reference: str | None = Field(
        default=None,
        max_length=500,
    )
    observed_at: datetime | None = None
    verified: bool = False

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.verified and not self.source_reference:
            raise ValueError(
                "Verified evidence requires a source reference"
            )

        if self.observed_at is not None:
            if self.observed_at.tzinfo is None:
                raise ValueError(
                    "Evidence timestamp must include timezone"
                )
            if self.observed_at > datetime.now(timezone.utc):
                raise ValueError(
                    "Evidence timestamp cannot be in the future"
                )

        return self


class FeedbackItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    feedback_id: str = Field(min_length=3, max_length=100)
    agent_domain: AgentDomain
    recommendation_reference: str = Field(
        min_length=3,
        max_length=150,
    )
    outcome: FeedbackOutcome
    explanation: str = Field(min_length=10, max_length=1500)
    evidence: list[FeedbackEvidence] = Field(
        default_factory=list,
        max_length=10,
    )


class LearningRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    review_reference: str = Field(min_length=3, max_length=100)
    feedback: list[FeedbackItem] = Field(
        min_length=1,
        max_length=25,
    )

    @model_validator(mode="after")
    def validate_unique_ids(self):
        ids = [item.feedback_id for item in self.feedback]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate feedback IDs are not allowed")
        return self


class LearningFinding(BaseModel):
    feedback_id: str
    agent_domain: AgentDomain
    outcome: FeedbackOutcome
    evidence_status: Literal[
        "source_referenced",
        "partially_referenced",
        "unverified",
        "no_evidence",
    ]
    assessment: Literal[
        "positive_feedback",
        "review_required",
        "insufficient_evidence",
        "safety_review_required",
    ]
    recommendation: str


class LearningResult(BaseModel):
    review_reference: str
    correlation_id: str | None = None
    feedback_count: int
    findings: list[LearningFinding]
    improvement_proposals: list[str]
    review_priority: Literal[
        "routine",
        "priority",
        "urgent",
    ]
    human_approval_required: bool = True
    training_performed: bool = False
    model_updated: bool = False
    feedback_persisted: bool = False
    external_action_performed: bool = False
    advisory_only: bool = True
    disclaimer: str


PROPOSALS = {
    FeedbackOutcome.helpful:
        "Retain this feedback as a candidate positive evaluation example after human verification.",
    FeedbackOutcome.inaccurate:
        "Review recommendation accuracy against authoritative evidence and investigate the underlying rules or data.",
    FeedbackOutcome.incomplete:
        "Review missing context, input coverage and explanation completeness.",
    FeedbackOutcome.outdated:
        "Review source freshness, effective dates and data refresh requirements.",
    FeedbackOutcome.unsafe:
        "Escalate to a qualified human safety reviewer before considering any change.",
}


def evidence_status(item: FeedbackItem) -> str:
    if not item.evidence:
        return "no_evidence"

    verified = sum(
        evidence.verified for evidence in item.evidence
    )

    if verified == len(item.evidence):
        return "source_referenced"
    if verified:
        return "partially_referenced"
    return "unverified"


def evaluate_learning(request: LearningRequest) -> LearningResult:
    findings = []
    proposals = []
    has_unsafe = False
    has_priority = False

    for item in request.feedback:
        status = evidence_status(item)

        if item.outcome == FeedbackOutcome.unsafe:
            assessment = "safety_review_required"
            has_unsafe = True
        elif status in ("no_evidence", "unverified"):
            assessment = "insufficient_evidence"
        elif item.outcome == FeedbackOutcome.helpful:
            assessment = "positive_feedback"
        else:
            assessment = "review_required"
            has_priority = True

        proposal = PROPOSALS[item.outcome]

        findings.append(
            LearningFinding(
                feedback_id=item.feedback_id,
                agent_domain=item.agent_domain,
                outcome=item.outcome,
                evidence_status=status,
                assessment=assessment,
                recommendation=proposal,
            )
        )

        if proposal not in proposals:
            proposals.append(proposal)

    if has_unsafe:
        priority = "urgent"
    elif has_priority:
        priority = "priority"
    else:
        priority = "routine"

    proposals.append(
        "A qualified human reviewer must validate all evidence "
        "and explicitly authorize any future implementation."
    )

    return LearningResult(
        review_reference=request.review_reference,
        feedback_count=len(request.feedback),
        findings=findings,
        improvement_proposals=proposals,
        review_priority=priority,
        disclaimer=(
            "This is a deterministic feedback review, not autonomous "
            "machine learning. Source references are supplied by users "
            "and are not independently authenticated. No training, "
            "model update, persistence, deployment or external action "
            "has occurred."
        ),
    )

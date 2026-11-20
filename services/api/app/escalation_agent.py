"""Deterministic, advisory-only agricultural escalation screening.

No database writes, messaging, dispatch or autonomous actions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Severity(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    critical = "critical"


class Indicator(str, Enum):
    severe_weather = "severe_weather"
    crop_damage = "crop_damage"
    pest_outbreak = "pest_outbreak"
    irrigation_shortage = "irrigation_shortage"
    market_disruption = "market_disruption"
    scheme_access_issue = "scheme_access_issue"
    immediate_personal_danger = "immediate_personal_danger"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    indicator: Indicator
    description: str = Field(min_length=10, max_length=1000)
    source_type: Literal[
        "field_observation",
        "verified_weather",
        "verified_market",
        "official_notice",
        "farmer_report",
        "other",
    ]
    source_reference: str | None = Field(default=None, max_length=500)
    observed_at: datetime | None = None
    verified: bool = False

    @model_validator(mode="after")
    def check_evidence(self):
        if self.verified and not self.source_reference:
            raise ValueError(
                "Verified evidence requires a source reference"
            )
        if self.observed_at is not None:
            observed = self.observed_at
            if observed.tzinfo is None:
                raise ValueError(
                    "Evidence timestamps must include a timezone"
                )
            if observed > datetime.now(timezone.utc):
                raise ValueError(
                    "Evidence timestamp cannot be in the future"
                )
        return self


class EscalationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_reference: str = Field(min_length=3, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    crop: str | None = Field(default=None, max_length=100)
    indicators: list[Evidence] = Field(min_length=1, max_length=10)
    notes: str | None = Field(default=None, max_length=1000)


class EscalationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_reference: str
    correlation_id: str | None = None
    severity: Severity
    priority_score: int
    confidence: Literal[
        "limited",
        "supported",
        "strong",
    ]
    reasons: list[str]
    recommended_actions: list[str]
    review_priority: str
    human_review_required: bool = True
    external_action_performed: bool = False
    notifications_sent: bool = False
    official_emergency_assessment: bool = False
    advisory_only: bool = True
    disclaimer: str


WEIGHTS = {
    Indicator.severe_weather: 35,
    Indicator.crop_damage: 25,
    Indicator.pest_outbreak: 30,
    Indicator.irrigation_shortage: 25,
    Indicator.market_disruption: 20,
    Indicator.scheme_access_issue: 10,
    Indicator.immediate_personal_danger: 80,
}

ACTIONS = {
    Indicator.severe_weather:
        "Review official weather warnings and local field conditions.",
    Indicator.crop_damage:
        "Arrange human agronomic review of documented crop damage.",
    Indicator.pest_outbreak:
        "Request qualified crop-health assessment before treatment.",
    Indicator.irrigation_shortage:
        "Review local water availability and irrigation options.",
    Indicator.market_disruption:
        "Verify market conditions using current authoritative sources.",
    Indicator.scheme_access_issue:
        "Verify scheme requirements with the responsible government office.",
    Indicator.immediate_personal_danger:
        "Prioritize immediate human safety assessment and contact appropriate local emergency services when warranted.",
}


def classify(score: int) -> Severity:
    if score >= 80:
        return Severity.critical
    if score >= 55:
        return Severity.high
    if score >= 30:
        return Severity.moderate
    return Severity.low


def evaluate_escalation(
    request: EscalationRequest,
) -> EscalationResult:
    unique = {}
    for item in request.indicators:
        existing = unique.get(item.indicator)
        if existing is None or (
            item.verified and not existing.verified
        ):
            unique[item.indicator] = item

    evidence = list(unique.values())

    score = min(
        100,
        sum(WEIGHTS[item.indicator] for item in evidence),
    )

    # Unverified reports must not be presented as confirmed facts.
    verified_count = sum(item.verified for item in evidence)

    if verified_count == len(evidence):
        confidence = "strong"
    elif verified_count:
        confidence = "supported"
    else:
        confidence = "limited"

    severity = classify(score)

    reasons = [
        (
            f"{item.indicator.value.replace('_', ' ').title()}: "
            f"{'source-referenced evidence' if item.verified else 'unverified report'}; "
            f"{item.description}"
        )
        for item in evidence
    ]

    actions = list(dict.fromkeys(
        ACTIONS[item.indicator] for item in evidence
    ))

    actions.append(
        "A responsible human reviewer must validate evidence, "
        "severity and any proposed intervention."
    )

    priority = {
        Severity.low: "Routine human review",
        Severity.moderate: "Prompt human review",
        Severity.high: "Priority human review",
        Severity.critical: "Immediate human review recommended",
    }[severity]

    return EscalationResult(
        case_reference=request.case_reference,
        severity=severity,
        priority_score=score,
        confidence=confidence,
        reasons=reasons,
        recommended_actions=actions,
        review_priority=priority,
        disclaimer=(
            "This is a rule-based screening recommendation, "
            "not a validated emergency diagnosis or official alert. "
            "Scores are heuristic, not calibrated probabilities. "
            "No notification, dispatch or external action has occurred."
        ),
    )

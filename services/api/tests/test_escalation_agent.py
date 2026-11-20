from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.escalation_agent import (
    Evidence,
    EscalationRequest,
    Indicator,
    Severity,
    classify,
    evaluate_escalation,
)


def evidence(
    indicator=Indicator.crop_damage,
    verified=False,
    **kwargs,
):
    values = {
        "indicator": indicator,
        "description": "Documented agricultural field observation",
        "source_type": "field_observation",
        "source_reference": "FIELD-001" if verified else None,
        "verified": verified,
    }
    values.update(kwargs)
    return Evidence(**values)


def request(*items):
    return EscalationRequest(
        case_reference="CASE-001",
        indicators=list(items),
    )


def test_low_severity():
    result = evaluate_escalation(
        request(evidence(Indicator.scheme_access_issue))
    )
    assert result.severity == Severity.low


def test_moderate_severity():
    result = evaluate_escalation(
        request(evidence(Indicator.severe_weather))
    )
    assert result.severity == Severity.moderate


def test_high_severity():
    result = evaluate_escalation(
        request(
            evidence(Indicator.severe_weather),
            evidence(Indicator.crop_damage),
        )
    )
    assert result.severity == Severity.high


def test_critical_severity():
    result = evaluate_escalation(
        request(evidence(Indicator.immediate_personal_danger))
    )
    assert result.severity == Severity.critical


def test_score_capped_at_100():
    result = evaluate_escalation(
        request(
            evidence(Indicator.immediate_personal_danger),
            evidence(Indicator.severe_weather),
        )
    )
    assert result.priority_score == 100


def test_duplicate_indicator_not_double_counted():
    result = evaluate_escalation(
        request(
            evidence(Indicator.crop_damage),
            evidence(Indicator.crop_damage),
        )
    )
    assert result.priority_score == 25


def test_verified_evidence_preferred():
    result = evaluate_escalation(
        request(
            evidence(Indicator.crop_damage),
            evidence(Indicator.crop_damage, verified=True),
        )
    )
    assert result.confidence == "strong"


def test_unverified_confidence_limited():
    result = evaluate_escalation(
        request(evidence())
    )
    assert result.confidence == "limited"


def test_all_verified_confidence_strong():
    result = evaluate_escalation(
        request(evidence(verified=True))
    )
    assert result.confidence == "strong"


def test_mixed_confidence_supported():
    result = evaluate_escalation(
        request(
            evidence(Indicator.crop_damage, verified=True),
            evidence(Indicator.severe_weather),
        )
    )
    assert result.confidence == "supported"


def test_verified_requires_reference():
    with pytest.raises(ValidationError):
        evidence(verified=True, source_reference=None)


def test_future_timestamp_rejected():
    with pytest.raises(ValidationError):
        evidence(
            observed_at=datetime.now(timezone.utc)
            + timedelta(days=1)
        )


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        evidence(observed_at=datetime.now())


def test_empty_indicators_rejected():
    with pytest.raises(ValidationError):
        request()


def test_too_many_indicators_rejected():
    with pytest.raises(ValidationError):
        request(*[evidence() for _ in range(11)])


def test_short_description_rejected():
    with pytest.raises(ValidationError):
        Evidence(
            indicator=Indicator.crop_damage,
            description="short",
            source_type="farmer_report",
        )


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        EscalationRequest(
            case_reference="CASE-001",
            indicators=[evidence()],
            autonomous_dispatch=True,
        )


def test_no_external_actions():
    result = evaluate_escalation(request(evidence()))
    assert result.human_review_required
    assert not result.external_action_performed
    assert not result.notifications_sent
    assert not result.official_emergency_assessment


def test_all_severity_boundaries():
    assert classify(0) == Severity.low
    assert classify(29) == Severity.low
    assert classify(30) == Severity.moderate
    assert classify(54) == Severity.moderate
    assert classify(55) == Severity.high
    assert classify(79) == Severity.high
    assert classify(80) == Severity.critical


def test_recommendations_present():
    result = evaluate_escalation(request(evidence()))
    assert result.recommended_actions
    assert "human reviewer" in result.recommended_actions[-1]


def test_advisory_disclaimer():
    result = evaluate_escalation(request(evidence()))
    assert result.advisory_only
    assert "not calibrated probabilities" in result.disclaimer

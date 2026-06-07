from dataclasses import dataclass

import pytest
from sentinel_intelligence.domain import AssessmentInput, RiskEngine, RiskFinding


@dataclass(frozen=True)
class Rule:
    rule_id: str = "test.rule"
    version: str = "1"

    def supports(self, assessment: AssessmentInput) -> bool:
        return assessment.action_type == "test.change"

    def evaluate(self, assessment: AssessmentInput) -> RiskFinding:
        return RiskFinding(
            rule_id=self.rule_id,
            score=75,
            severity="high",
            title="High blast radius",
            description="The test change affects dependencies.",
            evidence={"dependency_count": assessment.dependency_count},
            remediation="Use a maintenance window.",
        )


def test_engine_requires_reviewed_rules() -> None:
    with pytest.raises(ValueError):
        RiskEngine((), "empty")


def test_engine_returns_bounded_score_and_level() -> None:
    engine = RiskEngine((Rule(), Rule(rule_id="second")), "2026.06")
    score, level, findings = engine.evaluate(
        AssessmentInput("test.change", "resource", {}, 12, "production", True)
    )
    assert score == 100
    assert level == "high"
    assert len(findings) == 2

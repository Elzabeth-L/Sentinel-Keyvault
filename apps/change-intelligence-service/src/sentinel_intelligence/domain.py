from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AssessmentInput:
    action_type: str
    target_resource_id: str
    parameters: dict[str, object]
    dependency_count: int
    environment: str | None
    recoverable: bool


@dataclass(frozen=True, slots=True)
class RiskFinding:
    rule_id: str
    score: int
    severity: str
    title: str
    description: str
    evidence: dict[str, object]
    remediation: str | None


class RiskRule(Protocol):
    rule_id: str
    version: str

    def supports(self, assessment: AssessmentInput) -> bool: ...
    def evaluate(self, assessment: AssessmentInput) -> RiskFinding | None: ...


class RiskEngine:
    def __init__(self, rules: tuple[RiskRule, ...], rule_set_version: str) -> None:
        if not rules:
            raise ValueError("At least one reviewed risk rule is required")
        self._rules = rules
        self.rule_set_version = rule_set_version

    def evaluate(self, assessment: AssessmentInput) -> tuple[int, str, list[RiskFinding]]:
        findings = [
            finding
            for rule in self._rules
            if rule.supports(assessment)
            if (finding := rule.evaluate(assessment)) is not None
        ]
        score = min(100, sum(item.score for item in findings))
        level = "low" if score < 30 else "medium" if score < 70 else "high"
        return score, level, findings

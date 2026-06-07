from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EdgeCandidate:
    target_resource_id: str
    relationship_type: str
    dependency_strength: str
    confidence: float
    evidence_path: str


class RelationshipExtractor(Protocol):
    name: str
    version: str

    def supports(self, resource_type: str) -> bool: ...
    def extract(self, properties: dict[str, object]) -> list[EdgeCandidate]: ...


class ArmReferenceExtractor:
    """Extracts explicit ARM resource IDs from bounded Azure resource properties."""

    name = "arm-reference"
    version = "1.0.0"
    _ignored_suffixes = ("/providers/microsoft.insights/diagnosticsettings",)

    def supports(self, resource_type: str) -> bool:
        return resource_type.startswith("microsoft.")

    def extract(self, properties: dict[str, object]) -> list[EdgeCandidate]:
        candidates: dict[str, EdgeCandidate] = {}

        def visit(value: object, path: str, depth: int) -> None:
            if depth > 12:
                return
            if isinstance(value, dict):
                for key, child in value.items():
                    visit(child, f"{path}.{key}", depth + 1)
            elif isinstance(value, list):
                for index, child in enumerate(value[:1000]):
                    visit(child, f"{path}[{index}]", depth + 1)
            elif isinstance(value, str):
                normalized = value.strip().lower()
                if (
                    normalized.startswith("/subscriptions/")
                    and "/providers/" in normalized
                    and not normalized.endswith(self._ignored_suffixes)
                ):
                    candidates[normalized] = EdgeCandidate(
                        target_resource_id=normalized,
                        relationship_type="references",
                        dependency_strength="hard",
                        confidence=1.0,
                        evidence_path=path,
                    )

        visit(properties, "$", 0)
        return list(candidates.values())


DEFAULT_EXTRACTORS: tuple[RelationshipExtractor, ...] = (ArmReferenceExtractor(),)

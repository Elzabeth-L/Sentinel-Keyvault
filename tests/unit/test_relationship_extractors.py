from sentinel_relationship.extractors import ArmReferenceExtractor


def test_extracts_unique_arm_resource_references() -> None:
    extractor = ArmReferenceExtractor()
    target = (
        "/subscriptions/00000000-0000-0000-0000-000000000001/"
        "resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/app"
    )
    findings = extractor.extract({"identity": {"resourceId": target}, "duplicate": target})
    assert len(findings) == 1
    assert findings[0].target_resource_id == target.lower()
    assert findings[0].confidence == 1.0


def test_extractor_limits_recursive_depth() -> None:
    value: object = "/subscriptions/x/resourceGroups/y/providers/z/type/name"
    for _ in range(20):
        value = {"nested": value}
    assert ArmReferenceExtractor().extract({"root": value}) == []

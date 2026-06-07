from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    action_type: str
    display_name: str
    required_permission: str
    azure_permissions: tuple[str, ...]
    destructive: bool
    enabled: bool
    parameter_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    operation_id: str
    tenant_id: str
    actor_id: str
    target_resource_id: str
    parameters: dict[str, object]


class OperationExecutor(Protocol):
    definition: ActionDefinition

    async def validate_preconditions(self, context: ExecutionContext) -> None: ...
    async def execute(self, context: ExecutionContext) -> dict[str, object]: ...
    async def verify(self, context: ExecutionContext) -> dict[str, object]: ...


ACTION_CATALOG = (
    ActionDefinition(
        "azure.vm.start",
        "Start virtual machine",
        "operations.execute",
        ("Microsoft.Compute/virtualMachines/start/action",),
        False,
        False,
        {"type": "object", "additionalProperties": False},
    ),
    ActionDefinition(
        "azure.vm.stop",
        "Stop virtual machine",
        "operations.execute",
        ("Microsoft.Compute/virtualMachines/deallocate/action",),
        False,
        False,
        {"type": "object", "additionalProperties": False},
    ),
    ActionDefinition(
        "azure.vm.restart",
        "Restart virtual machine",
        "operations.execute",
        ("Microsoft.Compute/virtualMachines/restart/action",),
        False,
        False,
        {"type": "object", "additionalProperties": False},
    ),
    ActionDefinition(
        "kubernetes.deployment.restart",
        "Restart AKS deployment",
        "operations.execute",
        ("kubernetes:apps/deployments/patch",),
        False,
        False,
        {
            "type": "object",
            "required": ["namespace", "deployment"],
            "properties": {"namespace": {"type": "string"}, "deployment": {"type": "string"}},
            "additionalProperties": False,
        },
    ),
    ActionDefinition(
        "kubernetes.deployment.scale",
        "Scale AKS deployment",
        "operations.execute",
        ("kubernetes:apps/deployments/scale/patch",),
        False,
        False,
        {
            "type": "object",
            "required": ["namespace", "deployment", "replicas"],
            "properties": {
                "namespace": {"type": "string"},
                "deployment": {"type": "string"},
                "replicas": {"type": "integer", "minimum": 0},
            },
            "additionalProperties": False,
        },
    ),
    ActionDefinition(
        "azure.keyvault.secret.rotate",
        "Rotate Key Vault secret",
        "operations.execute",
        ("Microsoft.KeyVault/vaults/secrets/setSecret/action",),
        False,
        False,
        {"type": "object", "required": ["secret_name"], "additionalProperties": False},
    ),
    ActionDefinition(
        "azure.resource.tags.patch",
        "Update resource tags",
        "operations.execute",
        ("Microsoft.Resources/tags/write",),
        False,
        False,
        {"type": "object", "required": ["tags"], "additionalProperties": False},
    ),
)

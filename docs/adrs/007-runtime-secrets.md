# ADR 007: Runtime Secrets

Status: Accepted

## Context

Static application credentials and copied Kubernetes Secrets increase exposure and
rotation burden.

## Decision

Use AKS Workload Identity with dedicated service accounts and managed identities.
Access Key Vault through Azure Identity SDKs or the Secrets Store CSI Driver. Disable
Kubernetes Secret synchronization by default. VM workloads use VM managed identity.

## Consequences

Most platform access is credentialless and centrally governed. Federated credentials,
service account annotations, CSI rotation behavior, and Key Vault RBAC become required
deployment concerns.


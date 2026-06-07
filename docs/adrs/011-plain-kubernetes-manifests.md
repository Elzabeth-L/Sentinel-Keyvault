# ADR 011: Plain Kubernetes Manifests

Status: Accepted

Supersedes the Helm packaging portion of ADR 008.

## Context

Sentinel initially used a Helm chart for AKS packaging. The immediate deployment model
requires transparent files that an operator can inspect, replace Azure placeholders
in, and apply directly without a Helm release lifecycle.

## Decision

Maintain AKS resources as ordered plain YAML files under
`deploy/kubernetes/`. Use explicit `REPLACE_ME_*` placeholders for environment-specific
Azure values. Apply manifests with `kubectl` in the documented order.

The manifest set includes namespaces, ConfigMaps, Workload Identity service accounts,
Key Vault CSI projections, frontend and backend Deployments, workers, ClusterIP
Services, quotas, NetworkPolicies, and one Nginx gateway exposed through a Kubernetes
`LoadBalancer` Service.

Database migrations are packaged as a Docker image but are run from the Docker build
VM for the current simple Azure deployment. The previous Kubernetes migration Job was
removed to keep the first AKS deployment easier to understand and operate.

## Consequences

Deployment is easier to inspect and does not require Helm. Repeated workload structure
is more verbose, and environment overlays are manual. Direct LoadBalancer exposure is
simple but does not provide managed TLS/WAF. If multiple stamps, DNS/TLS, or frequent
environment-specific changes create material drift, introduce Kustomize, Gateway API,
Application Gateway, or another reviewed deployment layer in a future ADR without
changing the application contracts.

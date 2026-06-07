# ADR 008: Deployment Evolution

Status: Accepted

## Context

The required initial target is VM-based, while the production target is AKS.

## Decision

Package every component as an immutable container. Use Docker Compose on a hardened
private VM as a transitional production topology, backed by managed Azure data
services. Use the same images and configuration contracts in a private AKS cluster.
ADR 011 supersedes the original Helm packaging choice with plain Kubernetes manifests.

## Consequences

The initial release can ship without throwing away packaging work. Compose availability
and rollout limitations are accepted temporarily and documented in the service level.

# ADR 002: Multi-Tenant Identity

Status: Accepted

## Context

Users and managed Azure resources belong to different customer Entra tenants. Human
authorization and unattended Azure discovery/execution have different lifecycles.

## Decision

Use a provider-owned multi-tenant Entra application for user authentication. Represent
each customer tenant with an internal immutable ID. Use a separately consented,
customer-tenant automation identity for background Azure management-plane access.
Phase 1 permits certificate credentials held in Key Vault; a customer-side managed
identity connector is the future credentialless model.

## Consequences

Sentinel can perform durable background work without user refresh tokens. Onboarding
requires customer administration and careful certificate lifecycle management until
the connector model is delivered.


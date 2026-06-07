# ADR 003: Data Ownership and Tenant Isolation

Status: Accepted

## Context

A shared database is economical in Phase 1, but cross-tenant exposure and cross-service
schema coupling are critical risks.

## Decision

Use one PostgreSQL Flexible Server with service-owned schemas and roles. All
tenant-owned rows carry `tenant_id`; repositories filter by it and PostgreSQL RLS
enforces session tenant context. Foreign keys are used within a bounded context.
Cross-context references are contract-validated UUIDs, not cross-schema joins.

## Consequences

Tenant safety has multiple controls and schemas can later move to separate databases.
Cross-service UI queries require API composition or projections rather than direct SQL.


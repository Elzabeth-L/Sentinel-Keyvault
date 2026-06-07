# ADR 001: Control Plane and Service Boundaries

Status: Accepted

## Context

Sentinel coordinates discovery, analysis, approval, execution, and evidence. These
capabilities have different scaling, security, and failure characteristics.

## Decision

Build Sentinel as a regional Azure-hosted control plane with six independently
deployable bounded services and a Next.js web application. Separate synchronous APIs
from asynchronous workers. Services communicate through versioned HTTP and events and
own their persistence schemas.

## Consequences

Independent release and scale are possible, but distributed workflow, contract
compatibility, observability, and eventual consistency become mandatory engineering
concerns.


# Observability Architecture

## Telemetry Standard

All services use OpenTelemetry APIs and emit:

- structured JSON logs
- traces with W3C context
- RED metrics for APIs
- queue and worker metrics
- domain metrics for inventory, analysis, approvals, and operations

Azure Monitor/Application Insights is the initial backend. Instrumentation remains
vendor-neutral at application boundaries.

## Required Context

Every telemetry item includes, where applicable:

```text
service.name
service.version
deployment.environment
cloud.region
tenant.id_hash
correlation.id
operation.id
assessment.id
job.id
actor.type
outcome
```

Raw tenant names, access tokens, authorization headers, secret values, and full
resource property documents are excluded. Tenant IDs are hashed in general operations
telemetry; authorized audit records retain internal IDs.

## Health Endpoints

- `/health/live`: process is alive; no downstream calls.
- `/health/ready`: required local initialization complete and critical dependencies
  usable within a short timeout.
- `/version`: build SHA, semantic version, contract versions, migration compatibility.

Readiness failure removes a pod from traffic. It does not restart a healthy process
just because a remote dependency is briefly unavailable.

## Key Metrics

- request rate, error rate, duration by route and status class
- active DB connections, pool saturation, query duration, transaction retries
- Service Bus queue depth, age of oldest message, delivery count, DLQ count
- inventory duration, resources scanned/changed, tenant freshness
- relationship extraction duration, edge count, graph query size/latency
- assessment duration, risk distribution, stale/invalidated assessments
- approval age, expiry count, decision time
- operation success/failure, duration, retries, Azure throttling
- audit ingestion lag, export lag, integrity failures

Metrics must not use unbounded labels such as resource ID, user ID, or operation ID.

## Alerting

Alerts are symptom-oriented and route to an owned action group:

- availability/SLO burn rate
- sustained 5xx or latency
- inventory freshness breach
- Service Bus DLQ or message age
- operation failure spike
- audit ingestion/export lag
- PostgreSQL storage, CPU, connection, replica, or backup issue
- Key Vault/identity authorization failures
- certificate or federated credential expiry risk

Each production alert links to a runbook and has severity, owner, and expected response.

## Correlation

The edge accepts or generates `X-Correlation-ID`; services propagate it across HTTP,
events, database records, and Azure SDK client request IDs. Trace context is carried in
CloudEvents extensions. Azure request IDs are stored on operation attempts to support
provider escalation.


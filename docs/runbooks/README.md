# Production Runbooks

Runbooks are completed and exercised before production go-live.

| Runbook | Trigger |
|---|---|
| `tenant-access-revocation.md` | Customer requests immediate Sentinel revocation |
| `service-bus-dlq.md` | DLQ count or oldest-message alert |
| `postgresql-restore.md` | Corruption, accidental deletion, or DR exercise |
| `operation-stuck.md` | Operation heartbeat/timeout alert |
| `audit-integrity.md` | Hash-chain or export integrity failure |
| `credential-rotation.md` | Customer automation certificate rotation |
| `regional-failover.md` | Azure region outage declaration |

Every runbook must include owner, prerequisites, decision authority, commands or portal
steps, verification, rollback, evidence capture, and post-incident actions. Placeholder
runbooks are not considered production readiness evidence.


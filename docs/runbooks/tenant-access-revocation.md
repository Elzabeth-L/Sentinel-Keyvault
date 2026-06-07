# Tenant Access Revocation

Owner: Sentinel Security Operations

## Trigger

Customer request, suspected identity compromise, contract termination, or confirmed
cross-tenant security incident.

## Procedure

1. Record incident/change identifier and verify requester authority out of band.
2. Set tenant state to `suspended`; reject new API requests and worker claims.
3. Cancel queued operations and prevent running operations from starting new provider
   calls. Determine whether in-flight action cancellation is safer than completion.
4. Revoke/delete customer automation credentials and customer Azure role assignments.
5. Revoke enterprise application consent when directed by the customer.
6. Verify ARG/ARM token acquisition fails and no Service Bus messages remain active for
   the tenant.
7. Export required audit evidence and begin offboarding retention workflow.
8. Document timeline, affected operations, verification, and restoration criteria.

## Restoration

Restoration requires Security approval, renewed consent, new credential material,
scope/RBAC validation, and a successful read-only discovery dry run.


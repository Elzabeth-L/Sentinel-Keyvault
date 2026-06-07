# ADR 009: Backend-Owned OAuth Session

Status: Accepted

Supersedes the browser-token and no-user-refresh-token portions of ADR 002.

## Context

The existing Sentinel authentication implementation was replaced with the proven flow
from [`Sowrabh0-0/azure-inventory-saas`](https://github.com/Sowrabh0-0/azure-inventory-saas)
at commit `218ba3179e4f6ca99e036f60e49cea971ca6ec34`: backend-owned Microsoft
authorization code exchange with PKCE, an HTTP-only application session, and encrypted
refresh-token custody for delegated Azure inventory access.

Browser-held access tokens made every frontend module responsible for token acquisition
and did not support durable delegated Azure discovery without another customer
credential.

## Decision

Identity owns:

- Microsoft multi-tenant authorization code + PKCE login
- optional tenant-specific authority selection
- ID-token signature, issuer, audience, timestamp, `tid`, and `oid` validation
- an HTTP-only, signed, expiring Sentinel session cookie
- encrypted Microsoft refresh tokens scoped to the user and tenant
- refresh-token rotation and backend-only ARM token brokering

Other services never receive refresh tokens. They validate product sessions by calling
Identity and obtain only tenant/user/permission context. Inventory obtains short-lived
ARM access tokens through an authenticated internal Identity endpoint.

State-changing cookie-authenticated requests require a same-origin `Origin` or
`Referer`. Production cookies are `Secure`, `HttpOnly`, and `SameSite=Lax`.

## Consequences

The browser no longer uses MSAL or stores Microsoft access tokens. Sentinel can perform
delegated inventory refresh after login. Identity becomes a critical online dependency
for API authorization and ARM token refresh.

Refresh-token encryption and session-signing keys must be sourced from Key Vault,
rotated under a runbook, and never logged. Revocation, Conditional Access failures, and
expired consent surface as tenant reauthentication requirements.

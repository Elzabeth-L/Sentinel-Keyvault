# ADR 010: Personal Microsoft Account Isolation

Status: Accepted

## Context

Sentinel must support Microsoft personal accounts that own or can access Azure
subscriptions. Consumer identities may carry Microsoft's shared tenant ID
`9188040d-6c67-4c5b-b112-36a304b66dad`; using that value alone as a data boundary
would place unrelated personal users in one Sentinel tenant.

## Decision

Continue using `/common` login and delegated Azure Management access. Organizational
identities are isolated by Entra tenant ID. Consumer identities receive an internal
personal workspace isolated by `(tid, oid)`, and refresh tokens are redeemed through
`/common`. All downstream data remains scoped by the resulting internal tenant UUID.

The Entra app registration must allow accounts in any organizational directory and
personal Microsoft accounts. Azure RBAC remains authoritative for subscription and
resource visibility.

## Consequences

Personal users can authenticate without an invitation to an external organization,
provided their Microsoft account has Azure access. Two consumer accounts cannot share
Sentinel roles or data. Personal workspaces are single-user until a separate
workspace-sharing model is designed.

# Security Architecture

## Identity Planes

Sentinel has three separate identity planes:

1. **User identity:** Microsoft identity platform OIDC authorization code flow with
   backend-owned PKCE and an HTTP-only Sentinel session.
2. **Platform workload identity:** AKS Microsoft Entra Workload ID, or VM managed
   identity during transitional deployment.
3. **Customer Azure identity:** a customer-consented automation identity constrained
   to onboarded scopes.

Microsoft tokens are audience-specific and remain in Identity. Browser sessions are
accepted only as product authority; internal service credentials are never accepted as
user authority.

## Token Validation

Identity validates Microsoft ID-token signature and:

- expected audience
- issuer pattern and tenant ID
- `exp`, `nbf`, and acceptable clock skew
- authorized tenant onboarding status
- delegated scope or application role appropriate to the route

OpenID metadata and signing keys are cached with bounded refresh. Unknown signing key
IDs trigger one controlled refresh. Authentication fails closed.

The frontend never receives Microsoft access or refresh tokens. Identity issues a
signed, expiring, `HttpOnly`, `SameSite=Lax` Sentinel session cookie. State-changing
cookie-authenticated requests enforce same-origin request metadata.

Identity encrypts delegated Microsoft refresh tokens using a Key Vault-sourced Fernet
key. Refresh tokens are rotated when Microsoft returns replacements and are never
returned by product APIs.

## Authorization

Authorization has four gates:

1. Sentinel tenant membership is active.
2. Sentinel permission permits the product action.
3. Tenant policy and approval workflow permit the operation.
4. Customer Azure RBAC permits the automation identity at the target scope.

The permission catalog is stable and code checks permissions rather than role names.
High-risk operations support separation of duties, approval quorum, expiry, and
step-up authentication/Conditional Access policy at the Entra layer.

## Customer Onboarding and Least Privilege

Onboarding is explicit per customer tenant:

1. Customer administrator grants required application consent.
2. Sentinel validates tenant and publisher.
3. Customer selects subscriptions or resource groups.
4. Customer grants predefined custom Azure roles at those scopes.
5. Sentinel validates effective permissions and performs a dry-run inventory query.
6. An onboarding audit record captures consent, scopes, role definition versions, and
   actor.

Personal Microsoft accounts use the same `/common` login and delegated ARM consent.
Organizational accounts are isolated by Entra tenant ID. Consumer accounts are
isolated by `(tid, oid)` in separate internal Sentinel workspaces because Microsoft
consumer tokens can share one tenant ID. Azure RBAC still determines which
subscriptions and resources each user can discover.

Use separate discovery and execution role definitions. Discovery receives Resource
Graph query and read access. Execution roles are action-specific and are assigned only
where needed. Sentinel does not request Owner or User Access Administrator.

## Secrets and Key Vault

No source-controlled credentials or Kubernetes Secret objects are used for application
secrets. Preferred authentication is federated identity.

Current simple AKS flow:

```text
Pod
  -> Kubernetes service account token
  -> AKS OIDC issuer
  -> Microsoft Entra federated credential
  -> user-assigned managed identity
  -> Key Vault RBAC
  -> CSI-mounted secret/certificate file
```

Each service receives a dedicated Kubernetes service account. The current simple Azure
deployment uses one shared user-assigned managed identity; split identities per service
later when you harden least privilege. Pods requiring workload identity carry
`azure.workload.identity/use: "true"`. Key Vault access is granted per object class
and identity. Secret Store CSI Driver mounts files read-only; secret synchronization
to Kubernetes Secrets is used temporarily because the current services read
environment variables.

Applications should move toward mounted secret rotation or Azure SDK clients directly
with `DefaultAzureCredential`. Database access can move to Entra tokens later where
supported, avoiding a long-lived database password.

VM deployment uses the VM system-assigned managed identity and Key Vault SDK/VM
extension patterns, not copied `.env` secrets.

## Network Security

- Current simple ingress is the AKS `sentinel-gateway` LoadBalancer Service.
- DNS, HTTPS, Application Gateway/Gateway API, or WAF can be added later.
- PostgreSQL, Key Vault, and Storage may start with public access restricted as tightly
  as practical, then move to private endpoints when cost/complexity is acceptable.
- Network policies default-deny pod ingress/egress and allow named dependencies.
- Kubernetes API access uses Entra-integrated authorization.
- TLS 1.2 minimum; TLS 1.3 where supported. Internal HTTP remains encrypted when the
  threat model or compliance baseline requires it.

## Container and Supply Chain Security

- Minimal non-root images, read-only root filesystem, dropped Linux capabilities,
  seccomp runtime default, and no privilege escalation.
- Images are pulled from Docker Hub for the simple setup. Pin by digest later when
  release discipline matters.
- CI creates SBOM and provenance, scans dependencies/IaC/images, and signs artifacts.
- Future admission policy can reject unsigned images, privileged pods, mutable tags,
  missing resource limits, and disallowed registries.
- ACR can be introduced later if Docker Hub is no longer enough.

## Data Protection

- Azure-managed encryption at rest by default; customer-managed keys only when a
  concrete compliance requirement justifies lifecycle overhead.
- Sensitive columns are minimized and application-level encrypted where required.
- Logs apply allow-list serialization and redaction.
- Audit export uses immutable Blob Storage retention and restricted reader roles.
- Tenant offboarding revokes identity first, then executes policy-based export and
  deletion while retaining legally required audit evidence.

## Threats and Controls

| Threat | Primary controls |
|---|---|
| Cross-tenant data access | claim-derived tenant context, repository filters, RLS, tests |
| Forged/replayed operation | JWT validation, idempotency, immutable input hash, expiry |
| Privilege escalation | permission checks, scoped Azure roles, SoD approvals |
| Credential theft | workload identity, Key Vault, no local/persistent token storage |
| Arbitrary cloud mutation | versioned action allow-list and typed executors |
| SSRF against Azure metadata | egress policy, URL allow-list, managed SDK clients |
| Audit tampering | append-only API, hash chain, immutable export |
| Supply chain compromise | signed images, SBOM, scanning, admission policy |

## Break-Glass Access

Break-glass roles are separate cloud-only accounts protected by phishing-resistant
MFA, monitored use, just-in-time elevation, and mandatory incident review. Database
superuser and Key Vault administrative access are never routine service identities.

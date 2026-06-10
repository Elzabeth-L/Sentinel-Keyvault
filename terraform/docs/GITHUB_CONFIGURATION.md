# GitHub Configuration

## Environments

Create:

- `sentinel-dev`
- `sentinel-prod`

Restrict `sentinel-dev` to the `dev` branch and `sentinel-prod` to `master`.
Configure required reviewers on `sentinel-prod`.

## Environment variables

Set these separately in each GitHub environment:

| Variable | Development | Production |
|---|---|---|
| `AZURE_TENANT_ID` | `83474cb5-f1fa-4d06-906c-e5dad12ce3b9` | same |
| `AZURE_SUBSCRIPTION_ID` | `6b01db76-626a-44a2-8119-17682410914a` | `a8270be7-dabc-4d92-98db-26a55025b0df` |
| `AZURE_CLIENT_ID` | Dev bootstrap output | Prod bootstrap output |
| `TFSTATE_RESOURCE_GROUP` | `DEV-RG-1-TFSTATE` | `RG-1-TFSTATE` |
| `TFSTATE_STORAGE_ACCOUNT` | Dev bootstrap output | Prod bootstrap output |
| `NAME_SUFFIX` | Unique 4-8 lowercase characters | Different unique value |
| `RESOURCE_OWNER` | Team or owner | Team or owner |
| `COST_CENTER` | Approved value | Approved value |
| `OPERATOR_AND_CI_CIDRS` | JSON list such as `["203.0.113.10/32"]` | JSON list |
| `ALERT_EMAIL` | Alert recipient | Alert recipient |
| `ACR_NAME` | Dev Terraform output | Prod Terraform output |
| `AZURE_RUNNER_LABEL` | Stable-egress runner label | Stable-egress runner label |

The runner must have a stable public egress address included in
`OPERATOR_AND_CI_CIDRS` and the state-account firewall.

## Environment secrets

Required initially:

| Secret | Notes |
|---|---|
| `POSTGRES_BOOTSTRAP_PASSWORD` | Strong, unique per environment. Never reuse the application or Entra password. |

Optional and temporary:

| Secret | Notes |
|---|---|
| `DOCKERHUB_USERNAME` | Only if authenticated image import is required |
| `DOCKERHUB_TOKEN` | Short-lived read-only token; remove after import |

Do not add these to GitHub:

- Azure client secret
- ACR password
- Storage account key
- Entra application login secret
- Session signing key
- Token encryption key
- Internal API token
- Runtime database URL

Those runtime values belong directly in the environment Key Vault.

## OIDC

The bootstrap roots create one user-assigned identity per environment with a
federated subject tied to:

```text
repo:Elzabeth-L/Sentinel-Keyvault:environment:sentinel-dev
repo:Elzabeth-L/Sentinel-Keyvault:environment:sentinel-prod
```

GitHub exchanges its short-lived identity token for an Azure token. No
long-lived Azure credential is stored in GitHub.

# Deployment Checklist

## 1. Azure access

Log in to the confirmed tenant:

```powershell
az login --tenant 83474cb5-f1fa-4d06-906c-e5dad12ce3b9
az account list -o table
```

Both IDs must be visible:

```text
6b01db76-626a-44a2-8119-17682410914a
a8270be7-dabc-4d92-98db-26a55025b0df
```

The current CLI session used during implementation could access production but
could not see the development subscription. Correct that access before running
the dev bootstrap.

Run:

```powershell
./terraform/scripts/preflight.ps1 -Environment all
```

## 2. Existing production resources

The production subscription already contains `RG-1` and an existing minimal
Sentinel deployment. Do not approve the production Terraform apply until every
name collision is handled.

Choose one controlled path per existing resource:

- Import it into the matching Terraform address if its configuration should be
  retained.
- Rename the new Terraform-managed resource.
- Explicitly approve deletion and replacement after backup.

Never allow Terraform to discover this choice during an apply.

At minimum, inventory:

```powershell
az resource list `
  --subscription a8270be7-dabc-4d92-98db-26a55025b0df `
  --resource-group RG-1 `
  -o table
```

## 3. Bootstrap remote state

Apply `terraform/bootstrap/dev`, then `terraform/bootstrap/prod`, manually.
Record these outputs:

- State storage account name
- GitHub OIDC identity client ID

Configure the state-account firewall with the stable operator and CI egress
CIDRs.

## 4. GitHub environments

Follow [GITHUB_CONFIGURATION.md](GITHUB_CONFIGURATION.md).

Do not push the Terraform workflow until:

- Both OIDC identities exist.
- Both GitHub environments have their variables.
- The production environment has an approval rule.
- The stable runner egress CIDR is allow-listed.

## 5. Private Key Vault bootstrap

Key Vault is private-only. The current public operator machine cannot write
secrets after the private endpoint is enforced.

Use one of these controlled bootstrap methods:

1. Temporarily permit the operator's public IP, load the initial values, then
   immediately disable public access and verify the private endpoint.
2. Run a short-lived Kubernetes bootstrap Job in AKS with a dedicated workload
   identity and `Key Vault Secrets Officer`, then remove that role and Job.
3. Add a privately connected deployment runner later.

The initial values include:

- PostgreSQL runtime URL
- Entra application client secret
- Session signing key
- Token encryption key
- Internal API token
- Application Gateway certificate secret, when using Key Vault integration

Do not place these values in Terraform files, Git, workflow logs, or plan
artifacts.

## 6. TLS

Production users receive a Front Door managed certificate. Front Door initially
uses HTTP to the locked-down Application Gateway origin.

Development has no Front Door, so its Application Gateway must receive a valid
certificate for `dev.sentinel.vaultrix.in` before OAuth login is tested. Set the
versionless Key Vault certificate secret ID through the protected runtime
variable `TF_VAR_gateway_certificate_secret_id`.

## 7. Development first

1. Apply development infrastructure.
2. Import Docker Hub images into development ACR.
3. Configure Kubernetes manifests with ACR digests and workload identity client
   IDs.
4. Run the migration Job.
5. Validate DNS, TLS, login, inventory, audit, and restore procedures.
6. Review cost and monitoring.

Only then promote the same Terraform revision and image digests to production.

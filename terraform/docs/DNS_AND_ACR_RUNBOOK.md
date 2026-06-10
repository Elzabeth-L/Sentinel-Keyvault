# DNS and ACR Runbook

## Azure DNS delegation from GoDaddy

Production Terraform creates the Azure DNS child zone
`sentinel.vaultrix.in` and outputs four name servers.

In the existing GoDaddy `vaultrix.in` zone:

1. Add four `NS` records.
2. Use host/name `sentinel`.
3. Enter one Azure DNS name server in each record.
4. Keep the trailing dot if GoDaddy accepts it.
5. Do not change the registrar or unrelated `vaultrix.in` records.

Azure DNS then owns:

- `sentinel.vaultrix.in`
- `dev.sentinel.vaultrix.in`
- Front Door domain-validation records

## Existing image import

Run the import script once for each environment after ACR creation:

```powershell
./terraform/scripts/import-dockerhub-images.ps1 -AcrName <acr-name>
```

The script performs server-side ACR imports. It does not require Docker.

## New image builds

Pushes to:

- `dev` build images in development ACR.
- `master` build images in production ACR after the production environment
  approval.

Images are tagged with the Git commit SHA. Kubernetes deployment must use the
resolved digest for production promotion.

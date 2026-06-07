# Sentinel AKS Manifests

These are plain Kubernetes manifests for a simple AKS deployment. Helm is not used.

This folder assumes:

- one AKS cluster
- Docker Hub images
- one user-assigned managed identity for the Sentinel pods
- Key Vault Secrets Store CSI Driver
- one public AKS `LoadBalancer` Service named `sentinel-gateway`

## Replace Placeholders

Before applying anything, replace every placeholder:

```powershell
rg -n "REPLACE_ME_" deploy/kubernetes
```

Common values:

```text
REPLACE_ME_DOCKERHUB_USERNAME
REPLACE_ME_IMAGE_TAG
REPLACE_ME_SENTINEL_PUBLIC_IP
REPLACE_ME_KEY_VAULT_NAME
REPLACE_ME_SENTINEL_UAMI_CLIENT_ID
REPLACE_ME_PROVIDER_ENTRA_TENANT_ID
REPLACE_ME_IDENTITY_APP_CLIENT_ID
REPLACE_ME_POSTGRES_PRIVATE_IP_OR_CIDR
```

`REPLACE_ME_SENTINEL_PUBLIC_IP` is known only after Azure creates the
`sentinel-gateway` LoadBalancer. You can deploy once with placeholders, get the IP,
then update `01-config.yaml`, rebuild the web image with the real API URL, and restart
the web/identity pods.

## Images

Push these images to Docker Hub:

```text
<dockerhub>/sentinel-web:<tag>
<dockerhub>/sentinel-identity-service:<tag>
<dockerhub>/sentinel-inventory-service:<tag>
<dockerhub>/sentinel-relationship-service:<tag>
<dockerhub>/sentinel-change-intelligence-service:<tag>
<dockerhub>/sentinel-operations-service:<tag>
<dockerhub>/sentinel-audit-service:<tag>
```

The migration image is not deployed to AKS now. Build it on the Docker VM and run it
once to create/update PostgreSQL tables:

```text
<dockerhub>/sentinel-migration:<tag>
```

Build the web image with the public API URL baked in:

```text
NEXT_PUBLIC_API_BASE_URL=http://REPLACE_ME_SENTINEL_PUBLIC_IP/api/v1
```

`NEXT_PUBLIC_*` values are compiled into Next.js. Changing `01-config.yaml` later does
not change the already-built web image.

## Apply Order

```powershell
kubectl apply -f deploy/kubernetes/00-namespaces.yaml
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl apply -f deploy/kubernetes/02-service-accounts.yaml
kubectl apply -f deploy/kubernetes/03-secret-provider-classes.yaml
kubectl apply -f deploy/kubernetes/04-resource-governance.yaml
kubectl apply -f deploy/kubernetes/10-web.yaml
kubectl apply -f deploy/kubernetes/11-identity-service.yaml
kubectl apply -f deploy/kubernetes/12-inventory-service.yaml
kubectl apply -f deploy/kubernetes/13-relationship-service.yaml
kubectl apply -f deploy/kubernetes/14-change-intelligence-service.yaml
kubectl apply -f deploy/kubernetes/15-operations-service.yaml
kubectl apply -f deploy/kubernetes/16-audit-service.yaml
kubectl apply -f deploy/kubernetes/20-workers.yaml
kubectl apply -f deploy/kubernetes/40-network-policies.yaml
kubectl apply -f deploy/kubernetes/50-gateway-loadbalancer.yaml
```

Get the public IP:

```powershell
kubectl get svc sentinel-gateway -n sentinel-app
```

## Current Public IP Caveat

The checked-in gateway exposes HTTP on port `80`. This is fine for a first AKS smoke
test, but Microsoft login may require HTTPS for a public redirect URI. If Entra blocks
the raw `http://<public-ip>/auth/callback` redirect, keep the same manifests and add
DNS/TLS later.

For DNS/TLS later, change:

```text
SENTINEL_FRONTEND_URL=https://your-domain
SENTINEL_MICROSOFT_REDIRECT_URI=https://your-domain/auth/callback
SENTINEL_SESSION_COOKIE_SECURE=true
NEXT_PUBLIC_API_BASE_URL=https://your-domain/api/v1
```

## Secrets

Key Vault is the source of truth. The CSI provider syncs Key Vault values into
workload-specific Kubernetes Secrets because the current services read environment
variables. Do not commit real secret values to this repository.

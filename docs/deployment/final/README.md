# Sentinel Final Integrated Azure Deployment

This folder describes the fuller integrated Sentinel deployment target. It does not
replace the current minimal deployment guide.

Files:

- `sentinel-integrated-azure-deployment-guide.md` - end-to-end Azure resource creation
  guide with concrete portal configuration fields.
- `placeholders.md` - all placeholders and where each value comes from.
- `sentinel-integrated-architecture.drawio` - editable diagrams.net architecture and
  request-flow diagram using Azure-style draw.io shapes.

Architecture principle:

- One application resource group for simplicity.
- One VNet with dedicated subnets.
- Public entry through Azure Front Door Premium and Application Gateway WAF.
- All application workloads run on AKS.
- PostgreSQL, Key Vault, Storage, and ACR are private from the VNet.
- Managed identities and Workload Identity are used for service-to-Azure access.

variable "project" {
  description = "Short project name used to prefix every resource"
  type        = string
  default     = "ordermgmt"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "westeurope"
}

variable "resource_group_name" {
  description = "Name of an existing resource group to adopt instead of letting Terraform name/create a new one. Leave empty to fall back to \"rg-<project>-<environment>\". If set, `terraform import azurerm_resource_group.this <resource-id>` before the first apply (see CI-CD.md) so Terraform manages the existing group instead of trying to create a duplicate."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default = {
    project    = "order-management-supervision"
    managed_by = "terraform"
  }
}

# --------------------------------------------------------------------------
# Network / VPN to the LabelVie datacenter (specs.md §9.1, §9.3 "Tunnel")
# --------------------------------------------------------------------------

variable "vnet_address_space" {
  type    = list(string)
  default = ["10.20.0.0/16"]
}

variable "aca_subnet_prefix" {
  description = "Subnet delegated to the Container Apps environment"
  type        = string
  default     = "10.20.1.0/23"
}

variable "private_endpoints_subnet_prefix" {
  type    = string
  default = "10.20.3.0/26"
}

variable "gateway_subnet_prefix" {
  description = "Must be named GatewaySubnet — required by the VPN gateway"
  type        = string
  default     = "10.20.255.0/27"
}

variable "onprem_address_space" {
  description = "CIDR of the LabelVie on-premises datacenter network (reaches GOLD + mcp_gold)"
  type        = string
}

variable "onprem_vpn_gateway_public_ip" {
  description = "Public IP of the on-premises VPN device"
  type        = string
}

variable "mcp_gold_onprem_host" {
  description = "IP or FQDN of the mcp_gold server inside the LabelVie datacenter (flux F1b target)"
  type        = string
}

variable "mcp_gold_port" {
  type    = number
  default = 8001
}

variable "vpn_shared_key" {
  description = "IPsec pre-shared key for the site-to-site VPN connection"
  type        = string
  sensitive   = true
}

variable "deploy_vpn_gateway" {
  description = "Set to false to skip provisioning the (costly) VPN Gateway during early iterations"
  type        = bool
  default     = true
}

# --------------------------------------------------------------------------
# Container images
# --------------------------------------------------------------------------

variable "image_tag" {
  description = "Tag applied to all three service images (mcp-gold, mcp-relex-generix, agent)"
  type        = string
  default     = "latest"
}

# --------------------------------------------------------------------------
# Third-party connector credentials — placeholders only.
# Real values are set post-deployment directly in Key Vault (or via a
# separate, access-controlled pipeline), never committed to source control.
# See ../README.md "Passer un connecteur en mode réel".
# --------------------------------------------------------------------------

variable "gold_mode" {
  type    = string
  default = "stub"
}

variable "relex_mode" {
  type    = string
  default = "stub"
}

variable "generix_mode" {
  type    = string
  default = "stub"
}

variable "oracle_dsn" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "oracle_user" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "oracle_password" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "relex_client_id" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "relex_client_secret" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "relex_api_key" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "generix_api_key" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "grafana_admin_password" {
  type      = string
  default   = "changeme"
  sensitive = true
}

variable "teams_webhook_url" {
  description = "Incoming webhook URL of the Teams channel that receives supervision alerts (specs.md §9.1 \"Grafana ... route les alertes\"). Leave as placeholder to deploy with alerting disabled."
  type        = string
  default     = "changeme"
  sensitive   = true
}

# --------------------------------------------------------------------------
# Security toggles
# --------------------------------------------------------------------------

variable "enable_defender_for_cloud" {
  description = "Enable Microsoft Defender plans for Key Vault and Container Registry. Off by default: many orgs manage Defender centrally at subscription level."
  type        = bool
  default     = false
}

variable "enable_nsg_flow_logs" {
  description = "Enable NSG flow logs to a dedicated storage account (adds cost; on by default in prod)"
  type        = bool
  default     = false
}

variable "log_analytics_retention_days" {
  type    = number
  default = 90
}

variable "prometheus_retention_days" {
  description = "How long Prometheus keeps the historized indicator metrics (so past periods can be reviewed in Grafana)."
  type        = number
  default     = 400
}

variable "prometheus_storage_quota_gb" {
  description = "Quota (GiB) of the Azure File share backing Prometheus' persistent TSDB storage."
  type        = number
  default     = 50
}

variable "github_actions_principal_id" {
  description = "Object ID of the Azure AD app registration used by the GitHub Actions CI/CD pipeline (see CI-CD.md) to push images to ACR. Empty skips the role assignment — fine for the first bootstrap apply, before the app registration exists."
  type        = string
  default     = ""
}

variable "allowed_ip_ranges_for_grafana" {
  description = "CIDR ranges allowed to reach the public Grafana endpoint (empty = no extra restriction beyond Entra ID auth)"
  type        = list(string)
  default     = []
}

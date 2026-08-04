# RBAC-authorized Key Vault. Every credential the Azure-hosted services need
# is a secret here — never an env var literal, never in the repo (specs.md
# §9.4). Access control is identity-based (RBAC — Key Vault Administrator
# for the deployer, Key Vault Secrets User for each app identity), not
# network-based: Terraform itself writes the initial secrets from outside
# the VNet (Cloud Shell for the bootstrap, a GitHub-hosted runner for
# deploy-azure.yml), so public_network_access_enabled = false would lock
# the deployer out along with everyone else. The private endpoint below
# still gives Container Apps a private path from inside the VNet.

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "this" {
  name                          = "kv-${substr(replace(local.prefix, "-", ""), 0, 10)}${random_id.suffix.hex}"
  location                      = azurerm_resource_group.this.location
  resource_group_name           = azurerm_resource_group.this.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  enable_rbac_authorization     = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = true

  network_acls {
    default_action = "Allow"
    bypass         = "AzureServices"
  }

  tags = local.tags
}

resource "azurerm_private_endpoint" "keyvault" {
  name                = "pe-${local.prefix}-kv"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-kv"
    private_connection_resource_id = azurerm_key_vault.this.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "kv-dns"
    private_dns_zone_ids = [azurerm_private_dns_zone.keyvault.id]
  }
}

# Deployer needs write access to seed the initial (placeholder) secret
# values below — grant it explicitly rather than relying on ambient access.
resource "azurerm_role_assignment" "kv_admin_deployer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

locals {
  secrets = {
    "gold-mode"              = var.gold_mode
    "relex-mode"              = var.relex_mode
    "generix-mode"             = var.generix_mode
    "oracle-dsn"               = var.oracle_dsn
    "oracle-user"              = var.oracle_user
    "oracle-password"          = var.oracle_password
    "relex-client-id"          = var.relex_client_id
    "relex-client-secret"      = var.relex_client_secret
    "relex-api-key"            = var.relex_api_key
    "generix-api-key"          = var.generix_api_key
    "grafana-admin-password"   = var.grafana_admin_password
    "vpn-shared-key"           = var.vpn_shared_key
    "teams-webhook-url"        = var.teams_webhook_url
  }
}

# Values are seeded once from Terraform variables (defaulting to
# "changeme") and then rotated directly in Key Vault by operators — Terraform
# never fights that drift (see ../README.md "Passer un connecteur en mode réel").
resource "azurerm_key_vault_secret" "this" {
  for_each     = local.secrets
  name         = each.key
  value        = each.value
  key_vault_id = azurerm_key_vault.this.id

  depends_on = [azurerm_role_assignment.kv_admin_deployer]

  lifecycle {
    ignore_changes = [value]
  }
}

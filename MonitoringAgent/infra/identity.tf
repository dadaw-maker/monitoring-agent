# One user-assigned identity per Azure-hosted service — least privilege,
# no shared identity, no credentials embedded in images or env vars
# (specs.md §9.4 "identités et secrets gérés").

resource "azurerm_user_assigned_identity" "agent" {
  name                = "id-${local.prefix}-agent"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags
}

resource "azurerm_user_assigned_identity" "mcp_relex_generix" {
  name                = "id-${local.prefix}-mcp-relex-generix"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags
}

resource "azurerm_user_assigned_identity" "grafana" {
  name                = "id-${local.prefix}-grafana"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.tags
}

locals {
  aca_identities = {
    agent              = azurerm_user_assigned_identity.agent
    mcp_relex_generix  = azurerm_user_assigned_identity.mcp_relex_generix
    grafana            = azurerm_user_assigned_identity.grafana
  }
}

# ACR pull — Azure-hosted apps only. mcp_gold (on-prem) uses the scoped
# registry token defined in acr.tf instead.
resource "azurerm_role_assignment" "acr_pull" {
  for_each             = local.aca_identities
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = each.value.principal_id
}

# Key Vault Secrets User — read-only, no list/manage rights, no access to
# keys or certificates (specs.md §9.4 "lecture seule partout").
resource "azurerm_role_assignment" "kv_secrets_user" {
  for_each             = { agent = azurerm_user_assigned_identity.agent, mcp_relex_generix = azurerm_user_assigned_identity.mcp_relex_generix, grafana = azurerm_user_assigned_identity.grafana }
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = each.value.principal_id
}

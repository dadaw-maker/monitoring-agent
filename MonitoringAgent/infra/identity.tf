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

# AcrPush (not Contributor, not the ACR admin account) for the GitHub Actions
# CI/CD pipeline — the least privilege it needs to build and push the 3
# service images (CI-CD.md). Skipped on the very first bootstrap apply, when
# the app registration doesn't exist yet (var.github_actions_principal_id = "").
resource "azurerm_role_assignment" "acr_push_github_actions" {
  count                = var.github_actions_principal_id != "" ? 1 : 0
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPush"
  principal_id         = var.github_actions_principal_id
}

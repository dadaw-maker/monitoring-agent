# Log Analytics is both the Container Apps environment's log sink and the
# audit trail required by specs.md §9.4 ("Traçabilité — qu'a lu la
# supervision, et quand ?"): Key Vault and ACR diagnostic logs land here too.

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${local.prefix}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_analytics_retention_days
  tags                = local.tags
}

resource "azurerm_monitor_diagnostic_setting" "keyvault" {
  name                       = "diag-keyvault"
  target_resource_id         = azurerm_key_vault.this.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "AuditEvent"
  }

  metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "acr" {
  name                       = "diag-acr"
  target_resource_id         = azurerm_container_registry.this.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  enabled_log {
    category = "ContainerRegistryRepositoryEvents"
  }

  metric {
    category = "AllMetrics"
  }
}

# --------------------------------------------------------------------------
# Optional: Microsoft Defender for Cloud (off by default, see variables.tf)
# --------------------------------------------------------------------------

resource "azurerm_security_center_subscription_pricing" "key_vault" {
  count         = var.enable_defender_for_cloud ? 1 : 0
  tier          = "Standard"
  resource_type = "KeyVaults"
}

resource "azurerm_security_center_subscription_pricing" "container_registry" {
  count         = var.enable_defender_for_cloud ? 1 : 0
  tier          = "Standard"
  resource_type = "ContainerRegistry"
}

# --------------------------------------------------------------------------
# Optional: NSG flow logs (off by default, see variables.tf)
# --------------------------------------------------------------------------

resource "azurerm_storage_account" "flow_logs" {
  count                           = var.enable_nsg_flow_logs ? 1 : 0
  name                             = "st${replace(local.prefix, "-", "")}flow${random_id.suffix.hex}"
  resource_group_name              = azurerm_resource_group.this.name
  location                         = azurerm_resource_group.this.location
  account_tier                     = "Standard"
  account_replication_type         = "LRS"
  public_network_access_enabled    = false
  min_tls_version                  = "TLS1_2"
  tags                              = local.tags
}

resource "azurerm_network_watcher" "this" {
  count               = var.enable_nsg_flow_logs ? 1 : 0
  name                = "nw-${local.prefix}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_network_watcher_flow_log" "aca" {
  count                = var.enable_nsg_flow_logs ? 1 : 0
  name                 = "fl-${local.prefix}-aca"
  network_watcher_name = azurerm_network_watcher.this[0].name
  resource_group_name  = azurerm_resource_group.this.name

  network_security_group_id = azurerm_network_security_group.aca.id
  storage_account_id        = azurerm_storage_account.flow_logs[0].id
  enabled                    = true

  retention_policy {
    enabled = true
    days    = var.log_analytics_retention_days
  }

  traffic_analytics {
    enabled               = true
    workspace_id           = azurerm_log_analytics_workspace.this.workspace_id
    workspace_region       = azurerm_resource_group.this.location
    workspace_resource_id  = azurerm_log_analytics_workspace.this.id
  }
}

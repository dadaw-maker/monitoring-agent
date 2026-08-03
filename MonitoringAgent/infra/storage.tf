# Azure Files shares mounted into the Prometheus and Grafana container apps
# to carry their config (monitoring/prometheus/prometheus.yml and
# monitoring/grafana/provisioning/**) — content is pushed straight from this
# repo so the dashboard/scrape config in Azure always matches what's in git.

resource "azurerm_storage_account" "monitoring" {
  name                           = "st${substr(replace(local.prefix, "-", ""), 0, 14)}${random_id.suffix.hex}"
  resource_group_name            = azurerm_resource_group.this.name
  location                       = azurerm_resource_group.this.location
  account_tier                   = "Standard"
  account_replication_type       = "LRS"
  public_network_access_enabled  = false
  min_tls_version                = "TLS1_2"
  tags                            = local.tags
}

resource "azurerm_private_endpoint" "storage_file" {
  name                = "pe-${local.prefix}-stfile"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-stfile"
    private_connection_resource_id = azurerm_storage_account.monitoring.id
    subresource_names              = ["file"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "stfile-dns"
    private_dns_zone_ids = [azurerm_private_dns_zone.storage_file.id]
  }
}

resource "azurerm_storage_share" "prometheus_config" {
  name                 = "prometheus-config"
  storage_account_name = azurerm_storage_account.monitoring.name
  quota                = 1
}

resource "azurerm_storage_share" "grafana_provisioning" {
  name                 = "grafana-provisioning"
  storage_account_name = azurerm_storage_account.monitoring.name
  quota                = 1
}

resource "azurerm_storage_share_file" "prometheus_yml" {
  name             = "prometheus.yml"
  storage_share_id = azurerm_storage_share.prometheus_config.id
  source           = "${path.module}/../monitoring/prometheus/prometheus.yml"
}

locals {
  grafana_provisioning_files = fileset("${path.module}/../monitoring/grafana/provisioning", "**/*")
}

resource "azurerm_storage_share_file" "grafana_provisioning" {
  for_each         = local.grafana_provisioning_files
  name             = each.value
  storage_share_id = azurerm_storage_share.grafana_provisioning.id
  source           = "${path.module}/../monitoring/grafana/provisioning/${each.value}"
}

resource "azurerm_container_app_environment_storage" "prometheus_config" {
  name                         = "prometheus-config"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.monitoring.name
  share_name                   = azurerm_storage_share.prometheus_config.name
  access_key                   = azurerm_storage_account.monitoring.primary_access_key
  access_mode                  = "ReadOnly"
}

resource "azurerm_container_app_environment_storage" "grafana_provisioning" {
  name                         = "grafana-provisioning"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.monitoring.name
  share_name                   = azurerm_storage_share.grafana_provisioning.name
  access_key                   = azurerm_storage_account.monitoring.primary_access_key
  access_mode                  = "ReadOnly"
}

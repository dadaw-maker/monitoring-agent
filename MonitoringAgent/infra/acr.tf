# Container Registry — no admin user, pull-only access granted via managed
# identity + RBAC (specs.md §9.4 "identités et secrets gérés").

resource "azurerm_container_registry" "this" {
  name                          = "acr${replace(local.prefix, "-", "")}${random_id.suffix.hex}"
  resource_group_name           = azurerm_resource_group.this.name
  location                      = azurerm_resource_group.this.location
  sku                           = "Premium" # required for private endpoints
  admin_enabled                 = false
  public_network_access_enabled = false
  tags                          = local.tags
}

resource "azurerm_private_endpoint" "acr" {
  name                = "pe-${local.prefix}-acr"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.tags

  private_service_connection {
    name                           = "psc-acr"
    private_connection_resource_id = azurerm_container_registry.this.id
    subresource_names              = ["registry"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "acr-dns"
    private_dns_zone_ids = [azurerm_private_dns_zone.acr.id]
  }
}

# Scoped, non-admin credential for the on-premises mcp_gold host to pull its
# image (it cannot use an Azure managed identity since it does not run in
# Azure — specs.md §9.1). Scope map restricts it to a single read-only
# repository, never the whole registry.
resource "azurerm_container_registry_scope_map" "mcp_gold_pull" {
  name                    = "mcp-gold-pull-only"
  container_registry_name = azurerm_container_registry.this.name
  resource_group_name     = azurerm_resource_group.this.name
  actions                 = ["repositories/mcp-gold/content/read"]
}

resource "azurerm_container_registry_token" "mcp_gold_pull" {
  name                    = "mcp-gold-onprem"
  container_registry_name = azurerm_container_registry.this.name
  resource_group_name     = azurerm_resource_group.this.name
  scope_map_id            = azurerm_container_registry_scope_map.mcp_gold_pull.id
}

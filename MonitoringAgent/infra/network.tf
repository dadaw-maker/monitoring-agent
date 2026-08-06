# Network layout matches specs.md §9.1/§9.3: a dedicated VNet for the agent and
# the mcp_relex_generix server, a private-endpoints subnet for Key Vault/ACR,
# and a site-to-site VPN to the LabelVie datacenter — the *only* path allowed
# from Azure to the on-premises mcp_gold server (specs.md §9.4 "un seul flux
# autorisé, d'Azure vers le serveur MCP GOLD, sur un port unique").

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${local.prefix}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = var.vnet_address_space
  tags                = local.tags
}

resource "azurerm_subnet" "aca" {
  name                 = "snet-aca"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.aca_subnet_prefix]

  delegation {
    name = "aca-delegation"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "private_endpoints" {
  name                              = "snet-private-endpoints"
  resource_group_name               = azurerm_resource_group.this.name
  virtual_network_name              = azurerm_virtual_network.this.name
  address_prefixes                  = [var.private_endpoints_subnet_prefix]
  private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet" "gateway" {
  count                = var.deploy_vpn_gateway ? 1 : 0
  name                 = "GatewaySubnet" # name is fixed by Azure, must not be changed
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = [var.gateway_subnet_prefix]
}

# --------------------------------------------------------------------------
# NSG on the ACA subnet — default-deny, explicit allow-list only.
# --------------------------------------------------------------------------

resource "azurerm_network_security_group" "aca" {
  name                = "nsg-${local.prefix}-aca"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags

  security_rule {
    name                       = "AllowHttpsOutboundToSaaS"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "Internet"
    description                = "RELEX / Generix APIs (flux F0a, F0b)"
  }

  security_rule {
    name                       = "AllowOutboundToOnPremGold"
    priority                   = 110
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = tostring(var.mcp_gold_port)
    source_address_prefix      = "*"
    destination_address_prefix = var.onprem_address_space
    description                = "Seul flux autorisé vers mcp_gold on-premises (flux F1b)"
  }

  security_rule {
    name                       = "AllowAzureCloudOutbound"
    priority                   = 120
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "AzureCloud"
    description                = "Key Vault, ACR, Azure Monitor, Log Analytics (public endpoints)"
  }

  # Key Vault / ACR / Storage sit behind private endpoints in
  # snet-private-endpoints, and their private DNS zones are linked to this
  # VNet — so resources in snet-aca resolve those hostnames to the private
  # endpoint IPs, not public ones. That traffic matches neither AzureCloud
  # nor Internet above; without this rule it hits DenyAllOtherOutbound
  # (silently, which is exactly what a "timeout after 5s" managed-identity
  # Key Vault reference looks like — see azure-deployment.md).
  security_rule {
    name                       = "AllowOutboundToPrivateEndpoints"
    priority                   = 125
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = var.private_endpoints_subnet_prefix
    description                = "Key Vault / ACR / Storage private endpoints (snet-private-endpoints)"
  }

  security_rule {
    name                       = "DenyAllOtherOutbound"
    priority                   = 4096
    direction                  = "Outbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
    description                = "Ingress to Grafana is handled by the Container Apps platform load balancer, not this NSG"
  }
}

resource "azurerm_subnet_network_security_group_association" "aca" {
  subnet_id                 = azurerm_subnet.aca.id
  network_security_group_id = azurerm_network_security_group.aca.id
}

# --------------------------------------------------------------------------
# Site-to-site VPN to the LabelVie datacenter (specs.md §9.3 "Tunnel")
# --------------------------------------------------------------------------

resource "azurerm_public_ip" "vpn" {
  count               = var.deploy_vpn_gateway ? 1 : 0
  name                = "pip-${local.prefix}-vpngw"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_virtual_network_gateway" "this" {
  count               = var.deploy_vpn_gateway ? 1 : 0
  name                = "vgw-${local.prefix}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  type                = "Vpn"
  vpn_type            = "RouteBased"
  sku                 = "VpnGw1"
  tags                = local.tags

  ip_configuration {
    name                          = "vnetGatewayConfig"
    public_ip_address_id          = azurerm_public_ip.vpn[0].id
    private_ip_address_allocation = "Dynamic"
    subnet_id                     = azurerm_subnet.gateway[0].id
  }
}

resource "azurerm_local_network_gateway" "onprem" {
  count               = var.deploy_vpn_gateway ? 1 : 0
  name                = "lgw-labelvie-datacenter"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  gateway_address     = var.onprem_vpn_gateway_public_ip
  address_space       = [var.onprem_address_space]
  tags                = local.tags
}

resource "azurerm_virtual_network_gateway_connection" "onprem" {
  count                      = var.deploy_vpn_gateway ? 1 : 0
  name                       = "cn-${local.prefix}-to-labelvie"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  type                       = "IPsec"
  connection_protocol        = "IKEv2"
  virtual_network_gateway_id = azurerm_virtual_network_gateway.this[0].id
  local_network_gateway_id   = azurerm_local_network_gateway.onprem[0].id
  shared_key                 = var.vpn_shared_key
  tags                       = local.tags
}

# Explicit route: only the on-prem address space is routed through the
# gateway, nothing else — enforces the "un seul flux autorisé" principle
# at the routing layer, not just via NSG.
resource "azurerm_route_table" "aca" {
  name                           = "rt-${local.prefix}-aca"
  location                       = azurerm_resource_group.this.location
  resource_group_name            = azurerm_resource_group.this.name
  disable_bgp_route_propagation  = true
  tags                            = local.tags

  dynamic "route" {
    for_each = var.deploy_vpn_gateway ? [1] : []
    content {
      name                   = "to-labelvie-datacenter"
      address_prefix         = var.onprem_address_space
      next_hop_type          = "VirtualNetworkGateway"
    }
  }
}

resource "azurerm_subnet_route_table_association" "aca" {
  subnet_id      = azurerm_subnet.aca.id
  route_table_id = azurerm_route_table.aca.id
}

# --------------------------------------------------------------------------
# Private DNS zones for Key Vault / ACR private endpoints
# --------------------------------------------------------------------------

resource "azurerm_private_dns_zone" "keyvault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "keyvault" {
  name                  = "link-${local.prefix}-kv"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.keyvault.name
  virtual_network_id    = azurerm_virtual_network.this.id
}

resource "azurerm_private_dns_zone" "acr" {
  name                = "privatelink.azurecr.io"
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "acr" {
  name                  = "link-${local.prefix}-acr"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.acr.name
  virtual_network_id    = azurerm_virtual_network.this.id
}

resource "azurerm_private_dns_zone" "storage_file" {
  name                = "privatelink.file.core.windows.net"
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "storage_file" {
  name                  = "link-${local.prefix}-stfile"
  resource_group_name   = azurerm_resource_group.this.name
  private_dns_zone_name = azurerm_private_dns_zone.storage_file.name
  virtual_network_id    = azurerm_virtual_network.this.id
}

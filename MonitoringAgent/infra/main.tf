locals {
  prefix = "${var.project}-${var.environment}"
  tags   = var.tags
}

resource "random_id" "suffix" {
  byte_length = 3
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name != "" ? var.resource_group_name : "rg-${local.prefix}"
  location = var.location
  tags     = local.tags
}

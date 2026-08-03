terraform {
  required_version = ">= 1.7.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state (required for the CI/CD pipeline — GitHub Actions runs on a
  # fresh VM every time, it has no local state to work from). Values are
  # supplied at `terraform init` time via `-backend-config`, never hardcoded
  # here (see backend.hcl.example, DEPLOYMENT.md and CI-CD.md).
  backend "azurerm" {}
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }

  # Auth method is intentionally not hardcoded here:
  #  - locally: plain `az login` is enough, the provider picks it up automatically.
  #  - in CI: the workflow sets ARM_CLIENT_ID / ARM_TENANT_ID / ARM_SUBSCRIPTION_ID
  #    / ARM_USE_OIDC=true as job env vars (no client secret — GitHub's OIDC
  #    token, requested via the `id-token: write` permission, is exchanged
  #    for a short-lived Azure token). See ../CI-CD.md.
}

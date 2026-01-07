terraform {
  required_providers {
    port = {
      source  = "port-labs/port-labs"
      version = "~> 2.4.3"
    }
  }
}

provider "port" {
  client_id = var.port_client_id
  secret    = var.port_client_secret
  base_url  = "https://api.getport.io"
}

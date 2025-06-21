module "ocean-containerapp_example_azure-integration" {
  source  = "port-labs/ocean-containerapp/azure//examples/azure-integration"
  version = ">=0.0.4"

  port_client_id = "<PORT_CLIENT_ID>"
  port_client_secret = "<PORT_CLIENT_SECRET>"
  subscription_id = "xsa23scckw-1c79-26fa-a3f1-dnsadbjasd1"
}

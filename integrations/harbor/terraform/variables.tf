variable "port_client_id" {
  description = "Port Client ID (from Credentials page)"
  type        = string
  sensitive   = true
}

variable "port_client_secret" {
  description = "Port Client Secret (from Credentials page)"
  type        = string
  sensitive   = true
}

variable "port_region" {
  description = "Port region: 'eu' for Europe, 'us' for United States"
  type        = string
  default     = "eu"
  validation {
    condition     = contains(["eu", "us"], var.port_region)
    error_message = "Region must be 'eu' or 'us'."
  }
}

variable "event_listener" {
  type = object({
    type = string

    # POLLING
    resync_on_start = optional(bool)
    interval        = optional(number)

    # WEBHOOK
    app_host = optional(string)


    # KAFKA
    brokers                  = optional(list(string))
    security_protocol        = optional(list(string))
    authentication_mechanism = optional(list(string))
    kafka_security_enabled   = optional(list(bool))
    consumer_poll_timeout    = optional(list(number))
  })

  default = {
    type = "POLLING"
  }
}

variable "additional_secrets" {
  type = map(string)
  default = {}
}

variable "port" {
  type = object({
    client_id     = string
    client_secret = string
  })
}

variable "initialize_port_resources" {
  type    = bool
  default = false
}

variable "integration_version" {
  type    = string
  default = "latest"
}

variable "integration" {
  type = object({
    identifier = optional(string)
    type       = string
    config     = map(any)
  })
}

variable "assign_public_ip" {
  type    = bool
  default = true
}

variable "container_port" {
  default = 8000
}

variable "image_registry" {
  type    = string
  default = "ghcr.io/port-labs"
}

variable "location" {
  type    = string
  default = "West US 2 "
}

variable "subscription_id" {
  type    = string
  default = null
}

variable "resource_group_name" {
  type    = string
  default = null
}

variable "log_analytics_workspace_id" {
  type    = string
  default = null
}

variable "container_app_environment_id" {
  type    = string
  default = null
}

variable "cpu" {
  type    = string
  default = "1.0"
}

variable "memory" {
  type    = string
  default = "2Gi"
}

variable "image" {
  type    = string
  default = null
}

variable "min_replicas" {
  type    = number
  default = 1
}

variable "max_replicas" {
    type    = number
    default = 1
}

variable "user_assigned_identity_ids" {
  type    = list(string)
  default = []
}
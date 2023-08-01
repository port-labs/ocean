variable "certificate_domain_name" {
  type    = string
  default = ""
}
variable "token_mapping" {
  type    = map(list(string))
  default = {}
}
variable "vpc_id" {
  type = string
}
variable "subnets" {
  type = list(string)
}

variable "initialize_port_resources" {
  type    = bool
  default = false
}

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

variable "cluster_name" {
  type = string
}

variable "port" {
  type = object({
    client_id     = string
    client_secret = string
  })
}

variable "integration_version" {
  type    = string
  default = "latest"
}
variable "integration_identifier" {
  type    = string
  default = "my-gitlab-integration"
}
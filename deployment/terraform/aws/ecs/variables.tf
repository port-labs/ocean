variable "vpc_id" {
  type = string
}

variable "container_port" {
  default = 8000
}

variable "create_default_sg" {
  type    = bool
  default = true
}

variable "security_groups" {
  type    = list(string)
  default = []
}

variable "certificate_domain_name" {
  type    = string
  default = ""
}

variable "secrets" {
  type = map(string)
}

variable "subnets" {
  type = list(string)
}

variable "is_internal" {
  type    = bool
  default = false
}

variable "create_egress_default_sg" {
  type    = bool
  default = true
}

variable "egress_ports" {
  type    = list(number)
  default = []
}

variable "ecr_repo_url" {
  type    = string
  default = "ghcr.io/port-labs"
}

variable "integration_version" {
  type    = string
  default = "latest"
}

variable "logs_cloudwatch_retention" {
  description = "Number of days you want to retain log events in the log group."
  default     = 90
  type        = number
}

variable "logs_cloudwatch_group" {
  type    = string
  default = ""
}

variable "cpu" {
  default = 1024
}

variable "memory" {
  default = 2048
}

variable "network_mode" {
  default = "awsvpc"
}

variable "ecs_use_fargate" {
  type    = bool
  default = true
}

variable "cluster_name" {
  type = string
}

variable "assign_public_ip" {
  type    = bool
  default = true
}

variable "port" {
  type = object({
    client_id     = string
    client_secret = string
  })
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

variable "initialize_port_resources" {
  type    = bool
  default = false
}

variable "integration" {
  type = object({
    identifier = optional(string)
    type       = string
    config     = map(any)
  })
}

variable "lb_targ_group_arn" {
  type    = string
  default = ""
}
variable "additional_policy_statements" {
  type = list(object({
    actions   = list(string)
    resources = list(string)
  }))
  default = []
}

variable "allow_incoming_requests" {
  type = bool
  default = true
}
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

variable "ec2_create_task_execution_role" {
  description = "Set to true to create ecs task execution role to ECS EC2 Tasks."
  type        = bool
  default     = false
}

variable "logs_cloudwatch_group" {
  type    = string
  default = ""
}

variable "container_port" {
  default = 8000
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

variable "security_groups" {
  type    = list(string)
  default = []
}

variable "ecs_use_fargate" {
  type    = bool
  default = true
}

variable "subnets" {
  type = list(string)
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

    # WEBHOOK
    app_host = optional(string)

    # KAFKA
    brokers = optional(list(string))
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
    config     = any
  })
}

variable "additional_secrets" {
  type = list(object({
    name      = string
    valueFrom = string
  }))
  default = []
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
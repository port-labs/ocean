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

variable "additional_security_groups" {
  type    = list(string)
  default = []
}

variable "certificate_domain_name" {
  type    = string
  default = ""
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
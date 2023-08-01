variable "vpc_id" {
  type = string
}

variable "port" {
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

variable "subnets" {
  type = list(string)
}

variable "create_egress_default_sg" {
  type    = bool
  default = true
}

variable "egress_ports" {
  type    = list(number)
  default = []
}
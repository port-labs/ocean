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

variable "permissions" {
  type = object({
    actions      = optional(list(string))
    data_actions = optional(list(string))
    not_actions = optional(list(string))
    not_data_actions = optional(list(string))
  })
}

variable "permissions_scope" {
  type = list(string)
  default = null
}
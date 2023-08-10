variable "integration_version" {
  type    = string
  default = "latest"
  description = "The version of the integration to use"
}

variable "integration" {
  type = object({
    identifier = optional(string)
    type       = string
    config     = map(any)
  })
  description = "The integration to use"
}

variable "location" {
  type    = string
  default = "West US 2"
  description = "The location to create the user assigned identity in"
}

variable "subscription_id" {
  type    = string
  default = null
  description = "The scope of the user assigned identity and the scope of the role definition"
}

variable "resource_group_name" {
  type    = string
  default = null
  description = "The resource group name to associate the user assigned identity with"
}

variable "permissions" {
  type = object({
    actions      = optional(list(string))
    data_actions = optional(list(string))
    not_actions = optional(list(string))
    not_data_actions = optional(list(string))
  })
  description = "The permissions to grant to the user assigned identity"
}

variable "permissions_scope" {
  type = list(string)
  default = null
  description = "The scope of the permissions"
}

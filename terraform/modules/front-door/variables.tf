variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "origin_host_name" {
  type = string
}

variable "custom_domain" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

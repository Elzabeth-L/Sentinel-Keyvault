variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "environment" {
  type = string
}

variable "alert_email" {
  type    = string
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}

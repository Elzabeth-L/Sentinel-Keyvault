variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "workloads" {
  type = map(object({
    namespace       = string
    service_account = string
  }))
}

variable "tags" {
  type    = map(string)
  default = {}
}

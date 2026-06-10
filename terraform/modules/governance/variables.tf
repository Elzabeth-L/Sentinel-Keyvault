variable "name_prefix" {
  type = string
}

variable "subscription_id" {
  type = string
}

variable "allowed_locations" {
  type = list(string)
}

variable "required_tags" {
  type = list(string)
}

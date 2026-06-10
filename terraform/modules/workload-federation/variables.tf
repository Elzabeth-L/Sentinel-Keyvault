variable "resource_group_name" {
  type = string
}

variable "oidc_issuer_url" {
  type = string
}

variable "identities" {
  type = map(object({
    id              = string
    client_id       = string
    principal_id    = string
    namespace       = string
    service_account = string
  }))
}

variable "identity_keys" {
  type = set(string)
}

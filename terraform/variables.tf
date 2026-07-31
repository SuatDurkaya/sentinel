variable "gmail_app_password" {
  description = "Gmail app password for sending emails"
  type        = string
  sensitive   = true
}

variable "gmail_address" {
  type = string
}

variable "alert_to_email" {
  type = string
}
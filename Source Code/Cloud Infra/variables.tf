variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

# Your public IP with /32, e.g. "203.0.113.25/32". Restricts SSH.
variable "admin_cidr" {
  type = string
}

# Receives lockdown alerts
variable "alert_email" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}
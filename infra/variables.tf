variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}

variable "project" {
  type    = string
  default = "topal"
}

variable "env" {
  type    = string
  default = "dev"
}

# --- Aurora ---

variable "db_name" {
  type    = string
  default = "topal"
}

variable "db_username" {
  type    = string
  default = "topal"
}

variable "db_password" {
  type      = string
  sensitive = true
}

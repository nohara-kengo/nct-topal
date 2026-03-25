terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # state分離: terraform init -backend-config="key=dev/terraform.tfstate"
  backend "s3" {
    bucket = "topal-tfstate-265123441862"
    key    = "dev/terraform.tfstate"
    region = "ap-northeast-1"
  }
}

provider "aws" {
  region = var.aws_region
}

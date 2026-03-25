terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # prdはCIで -backend-config="key=prd/terraform.tfstate" で上書き
  backend "s3" {
    bucket = "topal-tfstate-265123441862"
    key    = "terraform.tfstate"
    region = "ap-northeast-1"
  }
}

provider "aws" {
  region = var.aws_region
}

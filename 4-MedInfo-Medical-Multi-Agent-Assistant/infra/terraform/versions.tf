# VALIDATE ONLY until explicitly approved: do not run `terraform apply` without the owner's go-ahead.
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Configure a remote state backend (S3 with encryption + locking) before the first apply.
  # backend "s3" {}
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      project     = "medinfo-assistant"
      environment = var.environment
      managed_by  = "terraform"
    }
  }
}

# AutoRAG Architect v4.0 — Terraform Version Constraints
# Run: terraform init (once per environment)

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state — enable after S3 bucket + DynamoDB table are created
  # backend "s3" {
  #   bucket         = "autorag-terraform-state"
  #   key            = "bootstrap/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "autorag-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "AutoRAG-Architect"
      Version     = "v4.0"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

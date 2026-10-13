# FinAgent AWS footprint (ap-southeast-1, same region as Supabase). VALIDATE ONLY unless the owner
# explicitly asks for `terraform apply` (CLAUDE.md). Postgres stays on Supabase; RDS is opt-in.
terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Remote state: create the bucket/table out of band, then `terraform init -backend-config=...`.
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "finagent"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

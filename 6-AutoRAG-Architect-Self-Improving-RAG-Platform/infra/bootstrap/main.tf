# Bootstrap — one-time setup: S3 remote state + DynamoDB lock
# TODO (Team 10): fill account-specific values before applying
# Run ONCE by leads only: terraform init && terraform apply

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "tf_state" {
  bucket = var.state_bucket_name
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket                  = aws_s3_bucket.tf_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_dynamodb_table" "tf_lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}

# ── AWS Secrets Manager — placeholder secrets ─────────────────────────────────
# ARNs output here are referenced by ecs_fargate + iam_core modules.
# Team 10: fill values after bootstrap with: aws secretsmanager put-secret-value

resource "aws_secretsmanager_secret" "supabase_url" {
  name = "autorag/${var.environment}/supabase_url"
}

resource "aws_secretsmanager_secret_version" "supabase_url" {
  secret_id     = aws_secretsmanager_secret.supabase_url.id
  secret_string = var.supabase_url
}

resource "aws_secretsmanager_secret" "supabase_key" {
  name = "autorag/${var.environment}/supabase_key"
}

resource "aws_secretsmanager_secret_version" "supabase_key" {
  secret_id     = aws_secretsmanager_secret.supabase_key.id
  secret_string = var.supabase_key
}

resource "aws_secretsmanager_secret" "supabase_db_url" {
  name = "autorag/${var.environment}/supabase_db_url"
}

resource "aws_secretsmanager_secret_version" "supabase_db_url" {
  secret_id     = aws_secretsmanager_secret.supabase_db_url.id
  secret_string = var.supabase_db_url
}

resource "aws_secretsmanager_secret" "euri_api_key" {
  name = "autorag/${var.environment}/euri_api_key"
}

resource "aws_secretsmanager_secret_version" "euri_api_key" {
  secret_id     = aws_secretsmanager_secret.euri_api_key.id
  secret_string = var.euri_api_key
}

resource "aws_secretsmanager_secret" "cohere_api_key" {
  name = "autorag/${var.environment}/cohere_api_key"
}

resource "aws_secretsmanager_secret_version" "cohere_api_key" {
  secret_id     = aws_secretsmanager_secret.cohere_api_key.id
  secret_string = var.cohere_api_key
}

# AutoRAG Architect v4.0 — Bootstrap Outputs
# S3 state bucket + DynamoDB lock outputs referenced by infra/main.tf backend block
# Secret Manager ARNs referenced by ecs_fargate + iam_core modules

output "state_bucket_name" {
  description = "S3 bucket name — use in infra/main.tf backend block"
  value       = aws_s3_bucket.tf_state.bucket
}

output "lock_table_name" {
  description = "DynamoDB lock table name — use in infra/main.tf backend block"
  value       = aws_dynamodb_table.tf_lock.name
}

output "region" {
  description = "AWS region these bootstrap resources were created in"
  value       = var.aws_region
}

output "secret_arn_supabase_url" {
  description = "ARN of the Supabase URL secret in Secrets Manager"
  value       = aws_secretsmanager_secret.supabase_url.arn
}

output "secret_arn_supabase_key" {
  description = "ARN of the Supabase key secret in Secrets Manager"
  value       = aws_secretsmanager_secret.supabase_key.arn
}

output "secret_arn_supabase_db_url" {
  description = "ARN of the Supabase DB URL secret in Secrets Manager"
  value       = aws_secretsmanager_secret.supabase_db_url.arn
}

output "secret_arn_euri_api_key" {
  description = "ARN of the EURI unified API key secret in Secrets Manager (covers Gemini + KiMi failover)"
  value       = aws_secretsmanager_secret.euri_api_key.arn
}

output "secret_arn_cohere_api_key" {
  description = "ARN of the Cohere API key secret in Secrets Manager"
  value       = aws_secretsmanager_secret.cohere_api_key.arn
}

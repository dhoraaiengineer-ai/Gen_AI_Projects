output "cluster_name" {
  value = module.eks.cluster_name
}

output "ecr_repositories" {
  value = { for k, r in aws_ecr_repository.app : k => r.repository_url }
}

output "github_cd_role_arn" {
  description = "Set as AWS_ROLE_ARN in the GitHub environment used by the CD workflow."
  value       = aws_iam_role.github_cd.arn
}

output "redis_endpoint" {
  description = "REDIS_URL host (TLS: rediss://<endpoint>:6379/0)."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "app_secret_arns" {
  value = { for k, s in aws_secretsmanager_secret.app : k => s.arn }
}

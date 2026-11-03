# AutoRAG Architect v4.0 — ECR Module Outputs

output "api_repository_url" {
  description = "ECR URL for the autorag-server API image (push SHA-tagged images here)"
  value       = aws_ecr_repository.api.repository_url
}

output "worker_repository_url" {
  description = "ECR URL for the LangGraph worker image"
  value       = aws_ecr_repository.worker.repository_url
}

output "api_repository_arn" {
  description = "ARN of the autorag-server ECR repository"
  value       = aws_ecr_repository.api.arn
}

output "worker_repository_arn" {
  description = "ARN of the worker ECR repository"
  value       = aws_ecr_repository.worker.arn
}

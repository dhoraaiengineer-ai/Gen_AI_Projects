# AutoRAG Architect v4.0 — ECS Fargate Module Outputs

output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "api_service_name" {
  description = "Name of the FastAPI ECS service (used in CodeDeploy config)"
  value       = aws_ecs_service.api.name
}

output "worker_service_name" {
  description = "Name of the LangGraph worker ECS service"
  value       = aws_ecs_service.worker.name
}

output "ecs_tasks_security_group_id" {
  description = "Security group ID for ECS tasks"
  value       = aws_security_group.ecs_tasks.id
}

output "api_log_group_name" {
  description = "CloudWatch log group for the API service"
  value       = aws_cloudwatch_log_group.api.name
}

output "worker_log_group_name" {
  description = "CloudWatch log group for the worker service"
  value       = aws_cloudwatch_log_group.worker.name
}

# AutoRAG Architect v4.0 — IAM Core Module Outputs

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role (used in ECS task definition)"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role (runtime permissions for the container)"
  value       = aws_iam_role.ecs_task.arn
}

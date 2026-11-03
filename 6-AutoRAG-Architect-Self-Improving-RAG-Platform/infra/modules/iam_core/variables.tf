# AutoRAG Architect v4.0 — IAM Core Module Variables

variable "project_name" {
  description = "Project identifier used in resource names"
  type        = string
}

variable "environment" {
  description = "Deployment environment: dev | staging | production"
  type        = string
}

variable "secret_arns" {
  description = "List of Secrets Manager ARNs the ECS task execution role must read"
  type        = list(string)
  default     = []
}

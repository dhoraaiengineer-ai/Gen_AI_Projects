# AutoRAG Architect v4.0 — ECS Fargate Module Variables

variable "project_name" {
  description = "Project identifier used in resource names"
  type        = string
}

variable "environment" {
  description = "Deployment environment: dev | staging | production"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs of private subnets where ECS tasks run"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID of the ALB (ECS SG allows inbound from this)"
  type        = string
}

variable "api_target_group_arn" {
  description = "ARN of the ALB target group for the FastAPI service"
  type        = string
}

variable "backend_image_url" {
  description = "Full ECR image URL with SHA tag for the FastAPI backend"
  type        = string
}

variable "worker_image_url" {
  description = "Full ECR image URL with SHA tag for the LangGraph worker"
  type        = string
}

variable "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  type        = string
}

variable "task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "api_cpu" {
  description = "CPU units for the API task (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Memory (MB) for the API task"
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "CPU units for the LangGraph worker task"
  type        = number
  default     = 1024
}

variable "worker_memory" {
  description = "Memory (MB) for the LangGraph worker task"
  type        = number
  default     = 2048
}

variable "api_desired_count" {
  description = "Number of API task instances to run"
  type        = number
  default     = 2
}

variable "worker_desired_count" {
  description = "Number of LangGraph worker instances to run"
  type        = number
  default     = 2
}

variable "secret_arns" {
  description = "Map of env var name → Secrets Manager ARN to inject into tasks"
  type        = map(string)
  default     = {}
}

variable "alb_listener_arn" {
  description = "ARN of the ALB listener"
  type        = string
}

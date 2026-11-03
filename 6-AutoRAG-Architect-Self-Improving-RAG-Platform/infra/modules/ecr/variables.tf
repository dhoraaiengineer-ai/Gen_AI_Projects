# AutoRAG Architect v4.0 — ECR Module Variables

variable "project_name" {
  description = "Project identifier used in resource names"
  type        = string
}

variable "environment" {
  description = "Deployment environment: dev | staging | production"
  type        = string
}

variable "image_retention_count" {
  description = "Number of untagged images to retain per repository"
  type        = number
  default     = 10
}

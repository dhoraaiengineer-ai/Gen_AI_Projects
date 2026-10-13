variable "region" {
  description = "AWS region (matches the Supabase project)."
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "production"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "name" {
  description = "Resource name prefix."
  type        = string
  default     = "finagent"
}

variable "vpc_cidr" {
  description = "VPC CIDR block."
  type        = string
  default     = "10.40.0.0/16"
}

variable "eks_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.33"
}

variable "node_instance_types" {
  description = "Managed node group instance types (API + MCP pods hold ML models and the cross-encoder in memory)."
  type        = list(string)
  default     = ["m7i.large"]
}

variable "node_min" {
  type    = number
  default = 2
}

variable "node_max" {
  type    = number
  default = 6
}

variable "github_repository" {
  description = "owner/repo allowed to assume the CI/CD role via GitHub OIDC."
  type        = string
  default     = "OWNER/finagent"
}

variable "enable_opensearch" {
  description = "OpenSearch domain for VECTOR_STORE=opensearch (pgvector on Supabase is the default)."
  type        = bool
  default     = false
}

variable "enable_rds" {
  description = "Self-managed Postgres (RDS) instead of Supabase. Off by default (ADR-004)."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  type    = number
  default = 30
}

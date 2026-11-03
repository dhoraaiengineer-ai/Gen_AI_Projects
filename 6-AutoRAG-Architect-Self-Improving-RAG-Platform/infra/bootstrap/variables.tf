# AutoRAG Architect v4.0 — Bootstrap Variables

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "ap-south-1"
}

variable "state_bucket_name" {
  description = "S3 bucket name for Terraform remote state"
  type        = string
}

variable "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking"
  type        = string
  default     = "autorag-tf-lock"
}

variable "environment" {
  description = "Deployment environment: dev | staging | production"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be one of: dev, staging, production"
  }
}

variable "project_name" {
  description = "Project identifier used in resource names"
  type        = string
  default     = "autorag"
}

variable "supabase_url" {
  description = "Supabase project URL (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "supabase_key" {
  description = "Supabase service role key (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "supabase_db_url" {
  description = "Supabase PostgreSQL connection string (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "euri_api_key" {
  description = "EURI unified API key — provides Gemini Flash 3.5 → KiMi K2.6 → Gemini 3.5 failover (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "cohere_api_key" {
  description = "Cohere Rerank v3 API key (stored in Secrets Manager)"
  type        = string
  sensitive   = true
}

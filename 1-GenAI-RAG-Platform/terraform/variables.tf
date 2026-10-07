variable "region" {
  description = "AWS region. Same as the Supabase project to avoid cross-region DB latency."
  type        = string
  default     = "ap-northeast-1"
}

variable "project" {
  description = "Name prefix for all resources."
  type        = string
  default     = "genai-rag"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "github_repo" {
  description = "GitHub repository allowed to deploy, as \"owner/name\"."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repo))
    error_message = "github_repo must look like \"owner/name\"."
  }
}

variable "create_github_oidc_provider" {
  description = "Set false if this AWS account already has the token.actions.githubusercontent.com OIDC provider."
  type        = bool
  default     = true
}

variable "vpc_cidr" {
  description = "VPC CIDR. Keep in sync with the ipBlock in k8s/networkpolicy.yaml."
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  type    = string
  default = "1.34"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 4
}

variable "node_desired_size" {
  type    = number
  default = 2
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "Who can reach the Kubernetes API. Restrict to your office/VPN IPs; GitHub-hosted runners need it open or a self-hosted runner."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "app_namespace" {
  type    = string
  default = "rag"
}

variable "prometheus_retention" {
  type    = string
  default = "15d"
}

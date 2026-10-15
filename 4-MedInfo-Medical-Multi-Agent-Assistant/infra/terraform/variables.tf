variable "region" {
  description = "Same region as the Supabase database (pooler aws-0-ap-southeast-2): latency and data residency stay together."
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "cluster_name" {
  type    = string
  default = "medinfo"
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "vpc_cidr" {
  description = "Keep in sync with the ALB ipBlock in deploy/k8s/networkpolicies.yaml."
  type        = string
  default     = "10.0.0.0/16"
}

variable "github_repository" {
  description = "owner/repo allowed to assume the CD role via GitHub OIDC."
  type        = string
  default     = "OWNER/REPO"
}

variable "github_environment" {
  description = "GitHub environment whose workflows may deploy (protect it with required reviewers)."
  type        = string
  default     = "production"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

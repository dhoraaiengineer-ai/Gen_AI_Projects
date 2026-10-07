# Values to copy into GitHub: Settings -> Secrets and variables -> Actions -> Variables.

output "aws_region" {
  value = var.region
}

output "eks_cluster_name" {
  description = "GitHub variable EKS_CLUSTER_NAME"
  value       = module.eks.cluster_name
}

output "ecr_repository_name" {
  description = "GitHub variable ECR_REPOSITORY"
  value       = module.ecr.repository_name
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "github_actions_role_arn" {
  description = "GitHub variable AWS_ROLE_ARN"
  value       = module.github_oidc.role_arn
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.region}"
}

output "grafana_access" {
  value = "kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80  (user: admin, password: terraform output -raw grafana_admin_password)"
}

output "grafana_admin_password" {
  value     = module.eks_addons.grafana_admin_password
  sensitive = true
}

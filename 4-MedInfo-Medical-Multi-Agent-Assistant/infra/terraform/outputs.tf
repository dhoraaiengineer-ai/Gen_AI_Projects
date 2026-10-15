output "region" {
  value = var.region
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "ecr_repository_urls" {
  value = { for k, r in aws_ecr_repository.app : k => r.repository_url }
}

output "github_cd_role_arn" {
  value = aws_iam_role.github_cd.arn
}

output "alb_controller_role_arn" {
  value = module.alb_controller_irsa.iam_role_arn
}

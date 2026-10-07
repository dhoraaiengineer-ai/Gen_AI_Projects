# IAM role that GitHub Actions assumes via OIDC: no long-lived AWS keys in GitHub.
# Only the given repo's "production" environment can assume it, and it can only push to one
# ECR repository and look up one EKS cluster. In-cluster rights come from an EKS access entry.

variable "name" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "create_oidc_provider" {
  type = bool
}

variable "ecr_repository_arn" {
  type = string
}

variable "eks_cluster_arn" {
  type = string
}

locals {
  oidc_url = "token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_oidc_provider ? 1 : 0
  url            = "https://${local.oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_oidc_provider ? 0 : 1
  url   = "https://${local.oidc_url}"
}

locals {
  oidc_provider_arn = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

resource "aws_iam_role" "github_actions" {
  name                 = "${var.name}-github-actions"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_url}:aud" = "sts.amazonaws.com"
          # Only workflows running in this repo's "production" environment (see .github/workflows/cd.yml).
          "${local.oidc_url}:sub" = "repo:${var.github_repo}:environment:production"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "deploy" {
  name = "deploy"
  role = aws_iam_role.github_actions.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrLogin"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*" # this action does not support resource scoping
      },
      {
        Sid    = "EcrPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:CompleteLayerUpload",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = var.ecr_repository_arn
      },
      {
        Sid      = "EksConnect"
        Effect   = "Allow"
        Action   = "eks:DescribeCluster"
        Resource = var.eks_cluster_arn
      },
    ]
  })
}

output "role_arn" {
  value = aws_iam_role.github_actions.arn
}

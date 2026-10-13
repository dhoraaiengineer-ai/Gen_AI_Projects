# GitHub Actions → AWS without long-lived keys: the CD workflow assumes this role via OIDC.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/main",
        "repo:${var.github_repository}:environment:${var.environment}",
      ]
    }
  }
}

resource "aws_iam_role" "github_cd" {
  name               = "${local.cluster}-github-cd"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

data "aws_iam_policy_document" "github_cd" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [for r in aws_ecr_repository.app : r.arn]
  }
  statement {
    sid       = "EksDescribe"
    actions   = ["eks:DescribeCluster"]
    resources = [module.eks.cluster_arn]
  }
  statement {
    sid       = "ReadAppSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [for s in aws_secretsmanager_secret.app : s.arn]
  }
}

resource "aws_iam_role_policy" "github_cd" {
  name   = "cd"
  role   = aws_iam_role.github_cd.id
  policy = data.aws_iam_policy_document.github_cd.json
}

# Cluster access for the CD role, scoped to the finagent namespace.
resource "aws_eks_access_entry" "github_cd" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.github_cd.arn
}

resource "aws_eks_access_policy_association" "github_cd" {
  cluster_name  = module.eks.cluster_name
  principal_arn = aws_iam_role.github_cd.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = "namespace"
    namespaces = ["finagent"]
  }
}

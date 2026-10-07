locals {
  name = "${var.project}-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

# ---------------------------------------------------------------- Network

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name = local.name
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]      # nodes and pods
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 48 + i)] # load balancers, NAT

  enable_nat_gateway = true
  single_nat_gateway = true # one NAT (~$45/mo) instead of one per AZ; trade-off: an AZ outage cuts egress

  # Lets the AWS Load Balancer Controller discover where to place load balancers.
  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}

# ---------------------------------------------------------------- Container registry

module "ecr" {
  source = "./modules/ecr"

  name = var.project
}

# ---------------------------------------------------------------- CI/CD identity (GitHub OIDC)

module "github_oidc" {
  source = "./modules/github-oidc"

  name                 = local.name
  github_repo          = var.github_repo
  create_oidc_provider = var.create_github_oidc_provider
  ecr_repository_arn   = module.ecr.repository_arn
  # Built from the name (not module.eks) to avoid a dependency cycle with the EKS access entry below.
  eks_cluster_arn = "arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${local.name}"
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------- Kubernetes cluster

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = local.name
  kubernetes_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs

  # Whoever runs `terraform apply` gets cluster-admin, so they can bootstrap and debug.
  enable_cluster_creator_admin_permissions = true

  addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
      # Enforces k8s/networkpolicy.yaml.
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
    eks-pod-identity-agent = {
      before_compute = true
    }
    aws-ebs-csi-driver = {
      pod_identity_association = [{
        role_arn        = aws_iam_role.ebs_csi.arn
        service_account = "ebs-csi-controller-sa"
      }]
    }
  }

  eks_managed_node_groups = {
    default = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.node_instance_types
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size
    }
  }

  # The CD role may only manage objects inside the app namespace.
  access_entries = {
    github_actions = {
      principal_arn = module.github_oidc.role_arn
      policy_associations = {
        app_namespace = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"
          access_scope = {
            type       = "namespace"
            namespaces = [var.app_namespace]
          }
        }
      }
    }
  }
}

# EBS CSI driver: persistent volumes for Prometheus.
resource "aws_iam_role" "ebs_csi" {
  name = "${local.name}-ebs-csi"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# ---------------------------------------------------------------- In-cluster platform

module "eks_addons" {
  source = "./modules/eks-addons"

  cluster_name         = module.eks.cluster_name
  region               = var.region
  vpc_id               = module.vpc.vpc_id
  app_namespace        = var.app_namespace
  prometheus_retention = var.prometheus_retention

  # Same files the local docker-compose monitoring stack uses.
  alert_rules_file      = "${path.root}/../monitoring/prometheus/alerts.yml"
  grafana_dashboard_dir = "${path.root}/../monitoring/grafana/dashboards"

  depends_on = [module.eks]
}

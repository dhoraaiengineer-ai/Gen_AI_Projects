data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs         = slice(data.aws_availability_zones.available.names, 0, 3)
  cluster     = "${var.name}-${var.environment}"
  repos       = ["finagent-backend", "finagent-frontend"]
  secret_keys = ["app"] # one JSON secret, synced into the `finagent-secrets` Kubernetes Secret
}

# ------------------------------------------------------------------ network
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.0"

  name            = local.cluster
  cidr            = var.vpc_cidr
  azs             = local.azs
  private_subnets = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, _ in local.azs : cidrsubnet(var.vpc_cidr, 8, 48 + i)]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true

  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}

# ------------------------------------------------------------------ EKS
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name               = local.cluster
  kubernetes_version = var.eks_version
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnets

  endpoint_public_access                   = true
  enable_cluster_creator_admin_permissions = true
  enabled_log_types                        = ["api", "audit", "authenticator"]

  addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = { before_compute = true }
    eks-pod-identity-agent = { before_compute = true }
  }

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = var.node_min
      max_size       = var.node_max
      desired_size   = var.node_min
      capacity_type  = "ON_DEMAND"
    }
  }
}

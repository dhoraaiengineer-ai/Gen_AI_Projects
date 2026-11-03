# Root Terraform config -- composes all modules
# Bootstrap outputs (state_bucket_name, lock_table_name) wired into backend block below.
# Secret ARNs from bootstrap are passed via secret_arn_* variables -- see infra/environments/*.tfvars.example.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    # Get bucket name from: terraform -chdir=infra/bootstrap output state_bucket_name
    bucket         = "autorag-tf-state"
    key            = "autorag/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "autorag-tf-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source       = "./modules/vpc"
  project_name = var.project_name
  environment  = var.environment
}

module "ecr" {
  source       = "./modules/ecr"
  project_name = var.project_name
  environment  = var.environment
}

module "alb" {
  source            = "./modules/alb"
  project_name      = var.project_name
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  certificate_arn   = var.certificate_arn
}

module "iam_core" {
  source       = "./modules/iam_core"
  project_name = var.project_name
  environment  = var.environment
  secret_arns = [
    var.secret_arn_supabase_url,
    var.secret_arn_supabase_key,
    var.secret_arn_supabase_db_url,
    var.secret_arn_euri_api_key,
    var.secret_arn_cohere_api_key,
  ]
}

module "ecs_fargate" {
  source                  = "./modules/ecs_fargate"
  project_name            = var.project_name
  environment             = var.environment
  vpc_id                  = module.vpc.vpc_id
  private_subnet_ids      = module.vpc.private_subnet_ids
  alb_security_group_id   = module.alb.alb_security_group_id
  api_target_group_arn    = module.alb.api_target_group_arn
  alb_listener_arn        = module.alb.https_listener_arn
  backend_image_url       = var.backend_image_url
  worker_image_url        = var.worker_image_url
  task_execution_role_arn = module.iam_core.ecs_task_execution_role_arn
  task_role_arn           = module.iam_core.ecs_task_role_arn
  secret_arns = {
    SUPABASE_URL              = var.secret_arn_supabase_url
    SUPABASE_SERVICE_ROLE_KEY = var.secret_arn_supabase_key
    SUPABASE_DB_URL           = var.secret_arn_supabase_db_url
    EURI_API_KEY              = var.secret_arn_euri_api_key
    COHERE_API_KEY            = var.secret_arn_cohere_api_key
  }
}

variable "project_name" {
  type    = string
  default = "autorag"
}

variable "environment" { type = string }
variable "certificate_arn" { type = string }
variable "backend_image_url" { type = string }
variable "worker_image_url" { type = string }

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

# Secret ARNs -- copy values from: terraform -chdir=infra/bootstrap output
variable "secret_arn_supabase_url" { type = string }
variable "secret_arn_supabase_key" { type = string }
variable "secret_arn_supabase_db_url" { type = string }
variable "secret_arn_euri_api_key" { type = string }
variable "secret_arn_cohere_api_key" { type = string }

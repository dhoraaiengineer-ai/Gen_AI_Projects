# ------------------------------------------------------------------ ECR
resource "aws_ecr_repository" "app" {
  for_each             = toset(local.repos)
  name                 = each.key
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 30 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 30 }
      action       = { type = "expire" }
    }]
  })
}

# ------------------------------------------------------------------ S3: documents + MLflow artefacts
resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${local.cluster}-artifacts-"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# ------------------------------------------------------------------ ElastiCache (Redis)
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.cluster}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.cluster}-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "Redis from EKS nodes"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.cluster}-redis"
  description                = "FinAgent rate limits, conversation memory, RAG answer cache"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = var.environment == "production" ? 2 : 1
  automatic_failover_enabled = var.environment == "production"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  port                       = 6379
}

# ------------------------------------------------------------------ Secrets Manager
# Values are set out of band (console/CLI by the owner), never in Terraform state.
resource "aws_secretsmanager_secret" "app" {
  for_each                = toset(local.secret_keys)
  name                    = "${local.cluster}/${each.key}"
  description             = "FinAgent runtime secrets (LLM keys, DATABASE_URL, SUPABASE_*, MCP_SERVICE_TOKEN, METRICS_TOKEN)"
  recovery_window_in_days = 7
}

# ------------------------------------------------------------------ CloudWatch
resource "aws_cloudwatch_log_group" "app" {
  name              = "/finagent/${var.environment}/app"
  retention_in_days = var.log_retention_days
}

# ------------------------------------------------------------------ optional: OpenSearch, RDS
resource "aws_opensearch_domain" "vectors" {
  count          = var.enable_opensearch ? 1 : 0
  domain_name    = "${var.name}-${var.environment}"
  engine_version = "OpenSearch_2.19"

  cluster_config {
    instance_type  = "r7g.large.search"
    instance_count = 2
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 50
  }

  vpc_options {
    subnet_ids = slice(module.vpc.private_subnets, 0, 2)
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }
}

resource "aws_db_subnet_group" "postgres" {
  count      = var.enable_rds ? 1 : 0
  name       = "${local.cluster}-postgres"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_db_instance" "postgres" {
  count                       = var.enable_rds ? 1 : 0
  identifier                  = "${local.cluster}-postgres"
  engine                      = "postgres"
  engine_version              = "17"
  instance_class              = "db.t4g.medium"
  allocated_storage           = 50
  storage_encrypted           = true
  db_name                     = "finagent"
  username                    = "finagent"
  manage_master_user_password = true # password lives in Secrets Manager, never in state
  db_subnet_group_name        = aws_db_subnet_group.postgres[0].name
  multi_az                    = var.environment == "production"
  backup_retention_period     = 7
  deletion_protection         = true
  skip_final_snapshot         = false
  final_snapshot_identifier   = "${local.cluster}-postgres-final"
}

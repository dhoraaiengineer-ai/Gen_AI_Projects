resource "aws_kms_key" "ecr" {
  description         = "${var.cluster_name} ECR encryption"
  enable_key_rotation = true
}

# One repository per image: backend (FastAPI) and frontend (nginx + static UI).
resource "aws_ecr_repository" "app" {
  for_each             = toset(["medinfo-backend", "medinfo-frontend"])
  name                 = each.key
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr.arn
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

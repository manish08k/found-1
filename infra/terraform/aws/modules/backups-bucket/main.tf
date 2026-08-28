terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.replica]
    }
  }
}

variable "name_prefix" { type = string }
variable "tags" { type = map(string) }
variable "replica_region" {
  type    = string
  default = "us-west-2"
}

resource "aws_s3_bucket" "backups" {
  bucket = "${var.name_prefix}-backups"
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    id     = "expire-old-backups"
    status = "Enabled"
    filter { prefix = "postgres/" }
    expiration { days = 90 } # k8s/29-backup-cronjob.yml also does its own 35-day cleanup within the bucket; this is the hard outer bound
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

# Cross-region replica bucket — this is what actually satisfies "backups
# survive a full region loss" in DR_RUNBOOK.md, not just versioning
# within one region. The aws.replica provider is configured in the ROOT
# module (main.tf) and passed into this module via the `providers = {}`
# argument on the module block — Terraform does not let a child module
# implicitly inherit an aliased provider.
resource "aws_s3_bucket" "backups_replica" {
  provider = aws.replica
  bucket   = "${var.name_prefix}-backups-replica"
  tags     = var.tags
}

resource "aws_s3_bucket_versioning" "backups_replica" {
  provider = aws.replica
  bucket   = aws_s3_bucket.backups_replica.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_iam_role" "replication" {
  name = "${var.name_prefix}-s3-replication-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
    }]
  })
  tags = var.tags
}

resource "aws_iam_role_policy" "replication" {
  name = "${var.name_prefix}-s3-replication-policy"
  role = aws_iam_role.replication.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["s3:GetReplicationConfiguration", "s3:ListBucket"]
        Effect   = "Allow"
        Resource = [aws_s3_bucket.backups.arn]
      },
      {
        Action   = ["s3:GetObjectVersionForReplication", "s3:GetObjectVersionAcl"]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.backups.arn}/*"]
      },
      {
        Action   = ["s3:ReplicateObject", "s3:ReplicateDelete"]
        Effect   = "Allow"
        Resource = ["${aws_s3_bucket.backups_replica.arn}/*"]
      },
    ]
  })
}

resource "aws_s3_bucket_replication_configuration" "backups" {
  depends_on = [aws_s3_bucket_versioning.backups]
  bucket     = aws_s3_bucket.backups.id
  role       = aws_iam_role.replication.arn

  rule {
    id     = "replicate-to-${var.replica_region}"
    status = "Enabled"
    destination {
      bucket        = aws_s3_bucket.backups_replica.arn
      storage_class = "STANDARD_IA"
    }
  }
}

output "bucket_name" { value = aws_s3_bucket.backups.bucket }
output "replica_bucket_name" { value = aws_s3_bucket.backups_replica.bucket }

# Root Terraform config for AutoFlow's AWS infrastructure.
#
# This is the layer BELOW k8s/ — those manifests assume a cluster,
# database, and cache already exist; this is what actually creates them.
# Apply this first, then k8s/ manifests, then the app.
#
# State: use a remote backend (S3 + DynamoDB lock table) in real use —
# left as local here so this is reviewable without requiring you to
# already have that bootstrapped. Uncomment and fill in before first
# `terraform init` in a real account.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # backend "s3" {
  #   bucket         = "autoflow-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "autoflow-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
}

# Additional provider configurations, passed explicitly into the child
# modules that use them (Terraform does not let a child module implicitly
# inherit an aliased provider from its caller).
provider "aws" {
  alias  = "replica"
  region = "us-west-2" # cross-region backup replica target — see modules/backups-bucket
}

provider "aws" {
  alias  = "billing"
  region = "us-east-1" # AWS billing metrics/Budgets notifications only publish here regardless of your main region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "project" {
  type    = string
  default = "autoflow"
}

locals {
  name_prefix = "${var.project}-${var.environment}"
  tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "vpc" {
  source = "./modules/vpc"

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "eks" {
  source = "./modules/eks"

  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  tags               = local.tags
}

module "database" {
  source = "./modules/database"

  name_prefix        = local.name_prefix
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  # Only the EKS node security group may reach Postgres/Redis directly —
  # this is the Terraform-layer equivalent of k8s/27-network-policies.yml
  # (that policy governs pod-to-pod; this governs what can reach the
  # managed services from outside the cluster network at all).
  allowed_security_group_id = module.eks.node_security_group_id
  tags                      = local.tags
}

module "backups_bucket" {
  source = "./modules/backups-bucket"
  providers = {
    aws.replica = aws.replica
  }

  name_prefix = local.name_prefix
  tags        = local.tags
}

module "cost_alerts" {
  source = "./modules/cost-alerts"
  providers = {
    aws.billing = aws.billing
  }

  name_prefix     = local.name_prefix
  monthly_budget  = var.monthly_budget_usd
  alert_email     = var.billing_alert_email
  tags            = local.tags
}

variable "monthly_budget_usd" {
  type        = number
  default     = 2000
  description = "Alert thresholds fire at 50/80/100/120% of this. Set to your real expected spend, not a guess — an unrealistic budget either never alerts or alerts constantly."
}

variable "billing_alert_email" {
  type        = string
  description = "Where cost-alert emails go. Required — no default, so this can't silently deploy with alerts going nowhere."
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "database_endpoint" {
  value     = module.database.postgres_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.database.redis_endpoint
  sensitive = true
}

output "backups_bucket_name" {
  value = module.backups_bucket.bucket_name
}

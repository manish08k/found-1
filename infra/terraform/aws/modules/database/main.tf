variable "name_prefix" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "allowed_security_group_id" { type = string }
variable "tags" { type = map(string) }

variable "postgres_instance_class" {
  type    = string
  default = "db.r6g.large"
}
variable "redis_node_type" {
  type    = string
  default = "cache.r6g.large"
}

resource "random_password" "postgres_master" {
  length  = 32
  special = false # RDS master password has character restrictions on some special chars; keep this simple and let app-level users have their own scoped passwords
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.name_prefix}-postgres-"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.allowed_security_group_id]
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-postgres-sg" })
}

# Master. Multi-AZ for automatic failover; PITR backups on top of the
# app-level nightly S3 dump (k8s/29-backup-cronjob.yml) — RDS snapshots
# cover fast point-in-time restore, the S3 dump covers portability and a
# second independent copy (see DR_RUNBOOK.md).
resource "aws_db_instance" "postgres_primary" {
  identifier     = "${var.name_prefix}-postgres-primary"
  engine         = "postgres"
  engine_version = "16.3"
  instance_class = var.postgres_instance_class

  allocated_storage     = 100
  max_allocated_storage = 1000 # storage autoscaling — a growing executions table shouldn't page anyone for a disk-full outage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "autoflow"
  username = "autoflow"
  password = random_password.postgres_master.result

  multi_az               = true
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.postgres.id]

  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:30-mon:05:30"

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-postgres-final-snapshot"

  performance_insights_enabled = true

  tags = var.tags
}

# Read replica — this is what api/routes/executions.py, workflows.py, and
# dlq.py's get_db_read() actually needs; set DATABASE_URL_REPLICA
# (k8s/00-namespace-config.yml) to this endpoint.
resource "aws_db_instance" "postgres_replica" {
  identifier          = "${var.name_prefix}-postgres-replica"
  replicate_source_db = aws_db_instance.postgres_primary.identifier
  instance_class      = var.postgres_instance_class
  storage_encrypted   = true

  vpc_security_group_ids = [aws_security_group.postgres.id]
  performance_insights_enabled = true

  tags = var.tags
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.name_prefix}-redis-"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.allowed_security_group_id]
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-redis-sg" })
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-redis-subnets"
  subnet_ids = var.private_subnet_ids
}

# Replication group (not a single cache cluster) so Redis has automatic
# failover — it's both the cache AND the Celery broker/result backend, so
# it being a single point of failure was flagged as a real gap earlier.
resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${var.name_prefix}-redis"
  description          = "AutoFlow Redis - cache + Celery broker"

  node_type            = var.redis_node_type
  num_cache_clusters    = 2
  automatic_failover_enabled = true
  multi_az_enabled     = true

  engine         = "redis"
  engine_version = "7.1"
  port           = 6379

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  snapshot_retention_limit = 7
  snapshot_window          = "05:00-06:00"

  tags = var.tags
}

output "postgres_endpoint" { value = aws_db_instance.postgres_primary.endpoint }
output "postgres_replica_endpoint" { value = aws_db_instance.postgres_replica.endpoint }
output "redis_endpoint" { value = aws_elasticache_replication_group.this.primary_endpoint_address }

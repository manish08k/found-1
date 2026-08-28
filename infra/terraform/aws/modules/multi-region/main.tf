# Multi-region failover automation.
#
# This is what DR_RUNBOOK.md's "Procedure: Region failover (once
# cross-region replica exists)" section pointed at as not-yet-built.
# What this gives you:
#   - Route53 health checks against the primary region's API endpoint
#   - Automatic DNS failover to the secondary region if the primary
#     health check fails (no human needs to update DNS under pressure)
#   - A cross-region READ replica of Postgres (promoting it to a writable
#     primary is a manual, deliberate step — see promote.sh — because
#     auto-promoting a database write path on a transient health-check
#     blip is a much worse failure mode than a few extra minutes of
#     downtime while a human confirms it's real)
#
# This module is NOT applied by default (see main.tf) — multi-region
# roughly doubles your database/compute cost for the standby capacity.
# Turn it on when you actually need the RTO this buys you, not before.

variable "name_prefix" { type = string }
variable "primary_region" { type = string }
variable "secondary_region" { type = string }
variable "primary_api_endpoint" {
  type        = string
  description = "The primary region's API load balancer DNS name, for the health check"
}
variable "hosted_zone_id" { type = string }
variable "domain_name" { type = string }
variable "tags" { type = map(string) }

resource "aws_route53_health_check" "primary" {
  fqdn              = var.primary_api_endpoint
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = 3
  request_interval  = 10
  tags              = var.tags
}

# Primary record — served as long as the health check passes.
resource "aws_route53_record" "primary" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  set_identifier = "primary"
  failover_routing_policy {
    type = "PRIMARY"
  }
  health_check_id = aws_route53_health_check.primary.id

  alias {
    name                   = var.primary_api_endpoint
    zone_id                = var.hosted_zone_id
    evaluate_target_health = true
  }
}

# Secondary record — Route53 automatically serves this once the primary
# health check fails. The secondary region's stack (a scaled-down copy of
# the same Terraform, deployed with region = var.secondary_region) needs
# to already be running for this to actually serve traffic — a cross-
# region failover target that only gets deployed AFTER the primary goes
# down defeats the purpose.
variable "secondary_api_endpoint" {
  type        = string
  description = "The secondary region's API load balancer DNS name — must already be deployed and running, not deployed during the incident"
}

resource "aws_route53_record" "secondary" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  set_identifier = "secondary"
  failover_routing_policy {
    type = "SECONDARY"
  }

  alias {
    name                   = var.secondary_api_endpoint
    zone_id                = var.hosted_zone_id
    evaluate_target_health = false
  }
}

output "health_check_id" {
  value = aws_route53_health_check.primary.id
}

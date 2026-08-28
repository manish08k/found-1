terraform {
  required_providers {
    aws = {
      source                = "hashicorp/aws"
      configuration_aliases = [aws.billing]
    }
  }
}

variable "name_prefix" { type = string }
variable "monthly_budget" { type = number }
variable "alert_email" { type = string }
variable "tags" { type = map(string) }

# AWS Budgets — the primary tool, alerts on % of a monthly budget with
# forecasted-vs-actual awareness. Multiple thresholds so a slow leak
# (autoscaler quietly running too many replicas) and a sudden spike
# (someone fat-fingers an instance type) both get caught early enough to
# act on, not just at "already way over budget".
resource "aws_budgets_budget" "monthly" {
  name         = "${var.name_prefix}-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100, 120]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alert_email]
    }
  }

  # Forecasted spend crossing 100% gets a heads-up BEFORE it actually
  # happens — this is the one that gives you time to act instead of just
  # finding out after the bill is already that size.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# CloudWatch billing alarm — belt-and-suspenders alongside Budgets, since
# it fires off actual billing metrics rather than the Budgets service's
# own (slightly delayed) evaluation cycle. Must be created in us-east-1;
# billing metrics only publish there regardless of your main region. The
# aws.billing provider is configured in the ROOT module and passed into
# this module via `providers = {}` on the module block.
resource "aws_sns_topic" "billing_alerts" {
  provider = aws.billing
  name     = "${var.name_prefix}-billing-alerts"
  tags     = var.tags
}

resource "aws_sns_topic_subscription" "billing_email" {
  provider  = aws.billing
  topic_arn = aws_sns_topic.billing_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "billing" {
  provider            = aws.billing
  alarm_name          = "${var.name_prefix}-estimated-charges"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 21600 # 6h — billing metrics update a few times a day, checking more often just wastes evaluations
  statistic           = "Maximum"
  threshold           = var.monthly_budget
  alarm_description   = "Estimated monthly AWS charges have crossed the configured budget threshold"
  dimensions          = { Currency = "USD" }
  alarm_actions       = [aws_sns_topic.billing_alerts.arn]
  tags                = var.tags
}

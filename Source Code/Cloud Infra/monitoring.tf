resource "aws_sns_topic" "alerts" {
  name = "vindelivery-alerts"
}

resource "aws_sns_topic_subscription" "admin_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# Counts log lines containing LOCKDOWN_TRIGGERED, written by the Lambda
resource "aws_cloudwatch_log_metric_filter" "lockdown" {
  name           = "lockdown-triggered"
  log_group_name = aws_cloudwatch_log_group.lambda.name
  pattern        = "\"LOCKDOWN_TRIGGERED\""

  metric_transformation {
    name      = "LockdownTriggered"
    namespace = "VinDelivery"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "lockdown" {
  alarm_name          = "vindelivery-lockdown"
  namespace           = "VinDelivery"
  metric_name         = "LockdownTriggered"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
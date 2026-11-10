resource "aws_ecs_cluster" "default" {
  name = var.ecs_cluster_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cloudwatch_log_group" "radar" {
  name              = var.log_group_name
  retention_in_days = 14

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_ecs_express_gateway_service" "radar" {
  service_name            = var.service_name
  cluster                 = aws_ecs_cluster.default.name
  execution_role_arn      = aws_iam_role.ecs_execution.arn
  infrastructure_role_arn = aws_iam_role.ecs_infrastructure.arn

  cpu               = "1024"
  memory            = "2048"
  health_check_path = "/health/live"

  primary_container {
    image          = var.bootstrap_image
    container_port = 8080

    aws_logs_configuration {
      log_group         = aws_cloudwatch_log_group.radar.name
      log_stream_prefix = "ecs"
    }
  }

  scaling_target {
    min_task_count            = 1
    max_task_count            = 1
    auto_scaling_metric       = "AVERAGE_CPU"
    auto_scaling_target_value = 60
  }

  tags = {
    Version = "managed-by-release-workflow"
  }

  lifecycle {
    prevent_destroy = true

    ignore_changes = [
      primary_container[0].image,
      tags["Version"]
    ]
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution,
    aws_iam_role_policy_attachment.ecs_infrastructure,
    aws_iam_role_policy.github_ecs,
    aws_iam_role_policy.github_pass_role
  ]
}

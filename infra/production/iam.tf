data "aws_iam_policy_document" "github_trust" {
  statement {
    sid     = "GitHubActionsOIDC"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:${var.github_owner}@${var.github_owner_id}/${var.github_repository}@${var.github_repository_id}:ref:refs/tags/v\u002a"
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "GitHubActionsRadarECRPush"
  description        = "GitHub OIDC role for publishing and deploying Radar Ferroviario."
  assume_role_policy = data.aws_iam_policy_document.github_trust.json

  tags = {
    Purpose = "github-actions-production-deployment"
  }
}

data "aws_iam_policy_document" "github_ecr" {
  statement {
    sid       = "ECRAuthentication"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "PublishAndInspectRadarImage"
    effect = "Allow"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer"
    ]

    resources = [
      aws_ecr_repository.radar.arn
    ]
  }
}

resource "aws_iam_role_policy" "github_ecr" {
  name   = "PushRadarImageToECR"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_ecr.json
}

data "aws_iam_policy_document" "github_ecs" {
  statement {
    sid    = "DeployRadarExpressService"
    effect = "Allow"

    actions = [
      "ecs:DescribeExpressGatewayService",
      "ecs:DescribeServiceDeployments",
      "ecs:DescribeServiceRevisions",
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:ListServiceDeployments",
      "ecs:MonitorExpressGatewayService",
      "ecs:RegisterTaskDefinition",
      "ecs:UpdateExpressGatewayService"
    ]

    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_ecs" {
  name   = "DeployRadarExpressService"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_ecs.json
}

data "aws_iam_policy_document" "ecs_task_trust" {
  statement {
    sid     = "AllowECSTasks"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "ecsTaskExecutionRole"
  description        = "Execution role for the Radar Ferroviario ECS task."
  assume_role_policy = data.aws_iam_policy_document.ecs_task_trust.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "github_pass_role" {
  statement {
    sid       = "PassOnlyRadarTaskExecutionRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.ecs_execution.arn]
  }
}

resource "aws_iam_role_policy" "github_pass_role" {
  name   = "PassRadarTaskExecutionRoleToECS"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_pass_role.json
}

data "aws_iam_policy_document" "ecs_infrastructure_trust" {
  statement {
    sid     = "AllowECSInfrastructureManagement"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_infrastructure" {
  name               = "ecsInfrastructureRoleForExpressServices"
  description        = "Infrastructure role for ECS Express Gateway Service."
  assume_role_policy = data.aws_iam_policy_document.ecs_infrastructure_trust.json
}

resource "aws_iam_role_policy_attachment" "ecs_infrastructure" {
  role       = aws_iam_role.ecs_infrastructure.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"
}

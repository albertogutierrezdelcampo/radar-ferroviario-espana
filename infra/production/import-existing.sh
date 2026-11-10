#!/usr/bin/env bash

set -euo pipefail

ACCOUNT_ID="778427063899"
SERVICE_ARN="arn:aws:ecs:eu-west-1:778427063899:service/default/radar-ferroviario"

run_import() {
  local address="$1"
  local identifier="$2"

  echo
  echo "Importing ${address}"
  echo "Identifier: ${identifier}"

  if terraform state show "$address" >/dev/null 2>&1; then
    echo "Already present in Terraform state"
    return 0
  fi

  terraform import "$address" "$identifier"
}

run_import \
  aws_ecr_repository.radar \
  radar-ferroviario

run_import \
  aws_ecr_lifecycle_policy.radar \
  radar-ferroviario

run_import \
  aws_iam_role.github_actions \
  GitHubActionsRadarECRPush

run_import \
  aws_iam_role_policy.github_ecr \
  GitHubActionsRadarECRPush:PushRadarImageToECR

run_import \
  aws_iam_role_policy.github_ecs \
  GitHubActionsRadarECRPush:DeployRadarExpressService

run_import \
  aws_iam_role_policy.github_pass_role \
  GitHubActionsRadarECRPush:PassRadarTaskExecutionRoleToECS

run_import \
  aws_iam_role.ecs_execution \
  ecsTaskExecutionRole

run_import \
  aws_iam_role_policy_attachment.ecs_execution \
  ecsTaskExecutionRole/arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

run_import \
  aws_iam_role.ecs_infrastructure \
  ecsInfrastructureRoleForExpressServices

run_import \
  aws_iam_role_policy_attachment.ecs_infrastructure \
  ecsInfrastructureRoleForExpressServices/arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices

run_import \
  aws_ecs_cluster.default \
  default

run_import \
  aws_cloudwatch_log_group.radar \
  /aws/ecs/default/radar-ferroviario-4994

run_import \
  aws_ecs_express_gateway_service.radar \
  "$SERVICE_ARN"

run_import \
  aws_budgets_budget.monthly \
  "${ACCOUNT_ID}:radar-ferroviario-monthly"

echo
echo "All imports completed."
echo "Run terraform plan and verify that no resource will be destroyed."

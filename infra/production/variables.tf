variable "aws_region" {
  description = "AWS deployment region."
  type        = string
  default     = "eu-west-1"
}

variable "aws_account_id" {
  description = "AWS account hosting the production infrastructure."
  type        = string
  default     = "778427063899"
}

variable "github_owner" {
  description = "GitHub repository owner."
  type        = string
  default     = "albertogutierrezdelcampo"
}

variable "github_repository" {
  description = "GitHub repository name."
  type        = string
  default     = "radar-ferroviario-espana"
}

variable "service_name" {
  description = "ECS Express Gateway Service name."
  type        = string
  default     = "radar-ferroviario"
}

variable "ecr_repository_name" {
  description = "Amazon ECR repository name."
  type        = string
  default     = "radar-ferroviario"
}

variable "ecs_cluster_name" {
  description = "ECS cluster hosting the Express service."
  type        = string
  default     = "default"
}

variable "bootstrap_image" {
  description = "Existing immutable image used while importing the ECS service."
  type        = string
  default     = "778427063899.dkr.ecr.eu-west-1.amazonaws.com/radar-ferroviario@sha256:8c7cb7ff01f265a6b28ac6227bccb82043d72c053e3cf095aee9e985aa744b1b"
}

variable "log_group_name" {
  description = "Existing CloudWatch log group used by the service."
  type        = string
  default     = "/aws/ecs/default/radar-ferroviario-4994"
}

variable "budget_limit_usd" {
  description = "Monthly AWS budget in USD."
  type        = number
  default     = 10
}

variable "budget_email" {
  description = "Email address receiving AWS Budget notifications."
  type        = string
  sensitive   = true
}

variable "github_owner_id" {
  description = "Immutable GitHub owner identifier used in OIDC subjects."
  type        = string
  default     = "131655812"
}

variable "github_repository_id" {
  description = "Immutable GitHub repository identifier used in OIDC subjects."
  type        = string
  default     = "1451564172"
}

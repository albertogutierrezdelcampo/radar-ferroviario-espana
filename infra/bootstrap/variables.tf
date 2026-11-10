variable "aws_region" {
  description = "AWS region used by the project."
  type        = string
  default     = "eu-west-1"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used only during bootstrap."
  type        = string
  default     = "personal"
}

variable "state_bucket_name" {
  description = "Globally unique S3 bucket for Terraform state."
  type        = string
  default     = "radar-ferroviario-tfstate-778427063899"
}

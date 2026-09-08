variable "cluster_arn" {
  description = "ARN of the existing ECS cluster."
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the existing ECS task execution role."
  type        = string
}

variable "image_ref" {
  description = "Digest-qualified container image reference to deploy."
  type        = string

  validation {
    condition     = can(regex("^[^[:space:]@]+@sha256:[0-9a-f]{64}$", var.image_ref))
    error_message = "image_ref must be an immutable repository@sha256 digest."
  }
}

variable "security_group_ids" {
  description = "Existing security groups for the service tasks."
  type        = list(string)
}

variable "subnet_ids" {
  description = "Existing private subnets for the service tasks."
  type        = list(string)
}

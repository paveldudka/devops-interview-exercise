variable "cluster_arn" {
  description = "ARN of the existing ECS cluster."
  type        = string
}

variable "execution_role_arn" {
  description = "ARN of the existing ECS task execution role."
  type        = string
}

variable "image_ref" {
  description = "Container image reference to deploy."
  type        = string
}

variable "security_group_ids" {
  description = "Existing security groups for the service tasks."
  type        = list(string)
}

variable "subnet_ids" {
  description = "Existing private subnets for the service tasks."
  type        = list(string)
}

output "deployed_image_ref" {
  description = "Image reference rendered into the task definition."
  value       = jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].image
}

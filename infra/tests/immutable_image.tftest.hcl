mock_provider "aws" {}

run "rejects_mutable_image" {
  command = plan

  variables {
    cluster_arn        = "arn:aws:ecs:us-west-2:123456789012:cluster/interview"
    execution_role_arn = "arn:aws:iam::123456789012:role/interview-execution"
    image_ref          = "example.invalid/interview-worker:latest"
    security_group_ids = ["sg-12345678"]
    subnet_ids         = ["subnet-12345678"]
  }

  expect_failures = [var.image_ref]
}

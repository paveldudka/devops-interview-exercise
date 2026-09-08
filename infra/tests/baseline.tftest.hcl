mock_provider "aws" {}

run "renders_supplied_image" {
  command = plan

  variables {
    cluster_arn        = "arn:aws:ecs:us-west-2:123456789012:cluster/interview"
    execution_role_arn = "arn:aws:iam::123456789012:role/interview-execution"
    image_ref          = "example.invalid/interview-worker@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    security_group_ids = ["sg-12345678"]
    subnet_ids         = ["subnet-12345678", "subnet-87654321"]
  }

  assert {
    condition     = output.deployed_image_ref == var.image_ref
    error_message = "The task definition must use the supplied image reference."
  }
}

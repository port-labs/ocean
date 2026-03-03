module "ocean_integration" {
  source       = "github.com/port-labs/Port-Ocean/deployment/terraform/aws/ecs"
  cluster_name = "my-ecs-cluster"
  vpc_id       = "vpc-12345678"
  subnets      = [
    "subnet-12345678",
    "subnet-87654321"
  ]

  // Optional Resource Settings
  ecs_use_fargate = true
  cpu             = 1024
  memory          = 2048

  port = {
    client_id     = "aabbccvalidclientidxxyyzz"
    client_secret = "aabbccvalidclientsercetxxyyzz"
  }

  integration = {
    type       = "gitlab"
    identifier = "my-gitlab-integration"
    config     = {
    }
  }

  additional_secrets             = {
    OCEAN__INTEGRATION__CONFIG__TOKEN_MAPPING = jsonencode({
      "glpat-ttookkeenn" = ["my-group/**"]
    })
  }
}

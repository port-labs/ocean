module "ocean_integration" {
  source       = "github.com/port-labs/Port-Ocean/deployment/terraform/aws/ecs"
  cluster_name = "my-ecs-cluster"
  vpc_id       = "vpc-12345678"
  subnets      = [
    "subnet-12345678",
    "subnet-87654321"
  ]

  port = {
    client_id     = "2r8d5egc56njs34d"
    client_secret = "e5f98sdh78b5n69ws4r3t0p1l2k9h8s7a6v5d4f"
  }

  integration = {
    type       = "gitlab"
    identifier = "my-gitlab-integration"
    config     = {
    }
  }

  additional_secrets             = {
    OCEAN__INTEGRATION__CONFIG__TOKEN_MAPPING = jsonencode({
      "glpat-jQNe7NYypFHefeaZo_ybA" = ["my-group/**"]
    })
  }
}

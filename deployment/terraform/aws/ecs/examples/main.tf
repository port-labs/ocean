module "ocean_integration" {
  source       = "../../ecs"
  cluster_name = "Port-ECS-Stg-01"
  vpc_id       = "vpc-0cf3be0bc1019dcf6"
  subnets      = [
    "subnet-0b1803e4cd66ad875",
    "subnet-0d42598347053f40e"
  ]

  port = {
    client_id     = "cktkrMVbS5mGlD7eqh9pqdNj1l998NxC"
    client_secret = "bUb1YRRONSp0z0ZeMvd3Gy3aLYDOMwHkpPh1ooTCd3T6QiLujGaoGkkqjS4AwCGR"
  }

  integration = {
    type       = "gitlab"
    identifier = "my-gitlab-integration"
    config     = {
    }
  }

  integration_version = "v0.1.5dev4"
  secrets             = {
    OCEAN__INTEGRATION__CONFIG__TOKEN_MAPPING = jsonencode({
      "glpat-jQNe7NYypFHNcaZo_ybA" = ["getport-labs/**"]
    })
  }
}
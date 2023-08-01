module "gitlab_integration" {
  source = "../../../modules/integrations/gitlab/ecs"

  cluster_name            = "<ECS_CLUSTEr_NAME>"
  certificate_domain_name = "<CERTIFICATE_DOMAIN_NAME>" # optional
  vpc_id                  = "<VPC_ID>"
  subnets                 = [
    "<SUBNET_ID_1>",
    "<SUBNET_ID_2>",
    "<SUBNET_ID_3>"
  ]

  port = {
    client_id     = "<CLIENT_ID>"
    client_secret = "<CLIENT_SECRET>"
  }

  token_mapping = {
    "<GitLab token>" = ["<GITLAB_PATH_TO_RUN_FOR_TOKEN>"] # e.g "glpat-jQNe7NYypFHNcaZo_ybA" = ["getport-labs/**"]
  }
}
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.1.0"
    }
    env = {
      source  = "tchupp/env"
      version = "0.0.2"
    }
    jsonschema = {
      source  = "bpedman/jsonschema"
      version = "0.2.1"
    }
  }
}

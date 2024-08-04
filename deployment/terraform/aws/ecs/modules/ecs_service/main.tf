locals {
  service_name     = "port-ocean-${var.integration.type}-${var.integration.identifier}"
  awslogs_group    = var.logs_cloudwatch_group == "" ? "/ecs/${local.service_name}" : var.logs_cloudwatch_group
  port_credentials = [
    {
      name      = "OCEAN__PORT"
      valueFrom = aws_ssm_parameter.ocean_port_credentials.name
    }
  ]

  env = [
    {
      name  = upper("OCEAN__INITIALIZE_PORT_RESOURCES"),
      value = var.initialize_port_resources ? "true" : "false"
    },
    {
      name  = upper("OCEAN__EVENT_LISTENER")
      value = jsonencode({
        for key, value in var.event_listener : key => value if value != null
      })
    },
    {
      name  = upper("OCEAN__INTEGRATION")
      value = jsonencode(var.integration)
    }
  ]
}

data "aws_region" "current" {}

resource "aws_ssm_parameter" "additional_secrets" {
  for_each = var.additional_secrets
  name     = "ocean.${var.integration.type}.${var.integration.identifier}.${lower(each.key)}"
  type     = "SecureString"
  value    = each.value
}

resource "aws_ssm_parameter" "ocean_port_credentials" {
  name  = "ocean.${var.integration.type}.${var.integration.identifier}.port_credentials"
  type  = "SecureString"
  value = jsonencode({
    client_secret : var.port.client_secret,
    client_id : var.port.client_id,
  })
}


resource "aws_cloudwatch_log_group" "log_group" {
  name              = local.awslogs_group
  retention_in_days = var.logs_cloudwatch_retention

  tags = {
    Name       = local.service_name
    Automation = "Terraform"
  }
}


data "aws_iam_policy_document" "ecs_assume_role_policy" {
  statement {
    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type        = "Service"
      identifiers = [
        "ecs-tasks.amazonaws.com",
        "ecs.amazonaws.com"
      ]
    }
  }
}

data "aws_iam_policy_document" "task_execution_role_policy" {
  dynamic "statement" {
    for_each = var.additional_policy_statements

    content {
      actions   = statement.value.actions
      resources = statement.value.resources
    }
  }

  statement {
    actions = [
      "ssm:GetParameters"
    ]

    resources = concat([
      aws_ssm_parameter.ocean_port_credentials.arn
    ], [
      for secret in aws_ssm_parameter.additional_secrets : secret.arn
    ])
  }

  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.log_group.arn}:*"
    ]
  }

  statement {
    actions = [
      "ecr:GetAuthorizationToken",
    ]

    resources = [
      "*"
    ]
  }
}

resource "aws_iam_role" "task_role" {
  name               = "ecs-${local.service_name}"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role_policy.json
}

resource "aws_iam_policy" "execution-policy" {
  name   = local.service_name
  policy = data.aws_iam_policy_document.task_execution_role_policy.json
}

resource "aws_iam_role" "task_execution_role" {
  name               = "ecs-execution-${local.service_name}"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role_policy.json
}

resource "aws_iam_role_policy_attachment" "attachment" {
  role       = aws_iam_role.task_execution_role.name
  policy_arn = aws_iam_policy.execution-policy.arn
}

resource "aws_ecs_task_definition" "service_task_definition" {
  family       = local.service_name
  network_mode = var.network_mode

  # Fargate requirements
  requires_compatibilities = compact([var.ecs_use_fargate ? "FARGATE" : ""])
  cpu                      = var.ecs_use_fargate ? var.cpu : ""
  memory                   = var.ecs_use_fargate ? var.memory : ""
  execution_role_arn       = aws_iam_role.task_execution_role.arn
  task_role_arn            = aws_iam_role.task_role.arn


  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode(
    [
      {
        image       = "${var.image_registry}/port-ocean-${var.integration.type}:${var.integration_version}",
        cpu         = var.cpu,
        memory      = var.memory,
        name        = local.service_name,
        networkMode = var.network_mode,
        environment = local.env,
        secrets     = concat(local.port_credentials, [
          for secret in keys(var.additional_secrets) : {
            name      = secret
            valueFrom = aws_ssm_parameter.additional_secrets[secret].name
          }
        ])
        logConfiguration = {
          logDriver = "awslogs",
          options   = {
            awslogs-create-group  = "true",
            awslogs-group         = "/ecs/${local.service_name}",
            awslogs-region        = data.aws_region.current.name,
            awslogs-stream-prefix = "ecs"
          }
        },
        portMappings = [
          {
            containerPort = var.container_port,
            hostPort      = var.container_port,
            protocol      = "tcp"
          }
        ]
      }
    ])
}

resource "aws_ecs_service" "ecs_service" {
  cluster = var.cluster_name

  deployment_circuit_breaker {
    enable   = "true"
    rollback = "true"
  }

  deployment_controller {
    type = "ECS"
  }

  name                               = local.service_name
  task_definition                    = aws_ecs_task_definition.service_task_definition.arn
  deployment_maximum_percent         = "200"
  deployment_minimum_healthy_percent = "100"
  desired_count                      = 1
  enable_ecs_managed_tags            = "false"
  enable_execute_command             = "false"
  health_check_grace_period_seconds  = "30"
  launch_type                        = "FARGATE"

  dynamic "load_balancer" {
    for_each = var.lb_targ_group_arn  != ""? [1] : []
    content {
      container_name   = local.service_name
      container_port   = var.container_port
      target_group_arn = var.lb_targ_group_arn
    }
  }

  network_configuration {
    assign_public_ip = var.assign_public_ip
    security_groups  = var.additional_security_groups
    subnets          = var.subnets
  }
  platform_version    = "LATEST"
  scheduling_strategy = "REPLICA"

  timeouts {
    create = "10m"
    update = "10m"
    delete = "20m"
  }
}

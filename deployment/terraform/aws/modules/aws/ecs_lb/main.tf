locals {
  protocol     = var.certificate_domain_name == "" ? "HTTP" : "HTTPS"
  port         = var.certificate_domain_name == "" ? "80" : "443"
  egress_ports = var.create_egress_default_sg ? concat([443, 9196], var.egress_ports) : var.egress_ports
}

data "aws_acm_certificate" "my-domain" {
  count  = var.certificate_domain_name != "" ? 1 : 0
  domain = var.certificate_domain_name
}

resource "aws_security_group" "default-ocean_sg" {
  count  = var.create_default_sg? 1 : 0
  vpc_id = var.vpc_id

  dynamic "ingress" {
    for_each = [var.port, local.port]
    content {
      description      = "TLS from VPC"
      from_port        = ingress.value
      to_port          = ingress.value
      protocol         = "tcp"
      cidr_blocks      = ["0.0.0.0/0"]
      ipv6_cidr_blocks = ["::/0"]
    }
  }

  dynamic "egress" {
    for_each = concat(local.egress_ports, [var.port])
    content {
      from_port        = egress.value
      to_port          = egress.value
      protocol         = "tcp"
      cidr_blocks      = ["0.0.0.0/0"]
      ipv6_cidr_blocks = ["::/0"]
    }
  }
}

resource "aws_lb" "ocean_lb" {
  internal           = false
  load_balancer_type = "application"
  security_groups    = var.create_default_sg ? concat(
    var.security_groups, [aws_security_group.default-ocean_sg[0].id]
  ) : var.security_groups
  subnets = var.subnets
}

resource "aws_lb_target_group" "ocean_tg" {
  port        = var.port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    interval            = 30
    path                = "/docs"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "lb_listener" {
  default_action {
    order            = "1"
    type             = "forward"
    target_group_arn = aws_lb_target_group.ocean_tg.arn
  }
  load_balancer_arn = aws_lb.ocean_lb.arn
  port              = local.port
  protocol          = local.protocol
  certificate_arn   = var.certificate_domain_name != ""? data.aws_acm_certificate.my-domain[0].arn : null
}
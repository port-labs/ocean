output "subnets" {
  value = aws_lb.ocean_lb.subnets
}

output "dns_name" {
  value = "${lower(local.lb_protocol)}://${var.certificate_domain_name == ""? aws_lb.ocean_lb.dns_name: var.certificate_domain_name}"
}

output "target_group_arn" {
  value = aws_lb_target_group.ocean_tg.arn
}

output "security_groups" {
  value = var.create_default_sg ? concat(
    var.additional_security_groups, [aws_security_group.default_ocean_sg[0].id]
  ) : var.additional_security_groups
}

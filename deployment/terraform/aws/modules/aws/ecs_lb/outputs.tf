output "subnets" {
  value = aws_lb.ocean_lb.subnets
}

output "dns_name" {
  value = "${lower(local.protocol)}://${var.certificate_domain_name == ""? aws_lb.ocean_lb.dns_name: var.certificate_domain_name}"
}

output "target_group_arn" {
  value = aws_lb_target_group.ocean_tg.arn
}

output "security_groups" {
  value = aws_lb.ocean_lb.security_groups
}
# AutoRAG Architect v4.0 — ALB Module Outputs

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "DNS name of the ALB (use this in Route 53 / CNAME)"
  value       = aws_lb.main.dns_name
}

output "api_target_group_arn" {
  description = "ARN of the FastAPI target group (used by ECS service)"
  value       = aws_lb_target_group.api.arn
}

output "alb_security_group_id" {
  description = "Security group ID of the ALB (ECS SG must allow inbound from this)"
  value       = aws_security_group.alb.id
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener"
  value       = aws_lb_listener.https.arn
}

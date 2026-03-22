output "api_url" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "aurora_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

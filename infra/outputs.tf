output "api_url" {
  value = aws_apigatewayv2_api.main.api_endpoint
}

output "task_queue_url" {
  value = aws_sqs_queue.task_queue.url
}

output "task_dlq_url" {
  value = aws_sqs_queue.task_dlq.url
}

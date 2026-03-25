resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

# --- Lambda Integrations ---

resource "aws_apigatewayv2_integration" "health" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.health.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "task_create" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.task_create.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "task_update" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.task_update.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "teams_webhook" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.teams_webhook.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "slack_webhook" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.slack_webhook.invoke_arn
  payload_format_version = "2.0"
}

# --- Routes ---

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"
}

resource "aws_apigatewayv2_route" "task_create" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /tasks"
  target    = "integrations/${aws_apigatewayv2_integration.task_create.id}"
}

resource "aws_apigatewayv2_route" "task_update" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "PUT /tasks/{taskId}"
  target    = "integrations/${aws_apigatewayv2_integration.task_update.id}"
}

resource "aws_apigatewayv2_route" "teams_webhook" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /webhook/teams"
  target    = "integrations/${aws_apigatewayv2_integration.teams_webhook.id}"
}

resource "aws_apigatewayv2_route" "slack_webhook" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /webhook/slack"
  target    = "integrations/${aws_apigatewayv2_integration.slack_webhook.id}"
}

# --- Lambda Permissions ---

resource "aws_lambda_permission" "health" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "task_create" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.task_create.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "task_update" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.task_update.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "teams_webhook" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.teams_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

resource "aws_lambda_permission" "slack_webhook" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

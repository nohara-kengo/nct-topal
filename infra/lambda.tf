# --- IAM Role ---

resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ssm" {
  name = "${local.name_prefix}-lambda-ssm"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/topal/*"
    }]
  })
}

# --- Lambda Layer (依存パッケージ) ---

resource "aws_lambda_layer_version" "deps" {
  filename            = "${path.module}/../dist/layer.zip"
  layer_name          = "${local.name_prefix}-deps"
  compatible_runtimes = ["python3.12"]
  source_code_hash    = filebase64sha256("${path.module}/../dist/layer.zip")
}

# --- 共通設定 ---

locals {
  name_prefix = "${var.project}-${var.env}"

  lambda_common_env = {
    SSM_PREFIX = "/topal"
  }
}

# --- Functions ---

resource "aws_lambda_function" "health" {
  function_name = "${local.name_prefix}-health"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/health.handler"
  runtime       = "python3.12"
  timeout       = 10

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  tags = { Name = "${local.name_prefix}-health" }
}

resource "aws_lambda_function" "task_create" {
  function_name = "${local.name_prefix}-task-create"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/task_create.handler"
  runtime       = "python3.12"
  timeout       = 120

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = local.lambda_common_env
  }

  tags = { Name = "${local.name_prefix}-task-create" }
}

resource "aws_lambda_function" "task_update" {
  function_name = "${local.name_prefix}-task-update"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/task_update.handler"
  runtime       = "python3.12"
  timeout       = 30

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = local.lambda_common_env
  }

  tags = { Name = "${local.name_prefix}-task-update" }
}

resource "aws_lambda_function" "teams_webhook" {
  function_name = "${local.name_prefix}-teams-webhook"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/teams_webhook.handler"
  runtime       = "python3.12"
  timeout       = 120

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = local.lambda_common_env
  }

  tags = { Name = "${local.name_prefix}-teams-webhook" }
}

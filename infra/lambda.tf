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

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
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
  lambda_common_env = {
    DATABASE_HOST = aws_rds_cluster.main.endpoint
    DATABASE_PORT = "5432"
    DATABASE_NAME = var.db_name
    DATABASE_USER = var.db_username
    DATABASE_PASSWORD = var.db_password
    SSM_PREFIX    = "/topal"
    AWS_REGION    = var.aws_region
  }

  lambda_vpc_config = {
    subnet_ids         = [aws_subnet.private_a.id, aws_subnet.private_c.id]
    security_group_ids = [aws_security_group.lambda.id]
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
  timeout       = 10

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  vpc_config {
    subnet_ids         = local.lambda_vpc_config.subnet_ids
    security_group_ids = local.lambda_vpc_config.security_group_ids
  }

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
  timeout       = 10

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  vpc_config {
    subnet_ids         = local.lambda_vpc_config.subnet_ids
    security_group_ids = local.lambda_vpc_config.security_group_ids
  }

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
  timeout       = 10

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  vpc_config {
    subnet_ids         = local.lambda_vpc_config.subnet_ids
    security_group_ids = local.lambda_vpc_config.security_group_ids
  }

  environment {
    variables = local.lambda_common_env
  }

  tags = { Name = "${local.name_prefix}-teams-webhook" }
}

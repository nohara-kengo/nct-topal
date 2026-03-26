# --- IAM Role ---

resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
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
      Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/topal/${var.env}/*"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_sqs" {
  name = "${local.name_prefix}-lambda-sqs"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
        ]
        Resource = aws_sqs_queue.task_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = aws_sqs_queue.task_queue.arn
      },
    ]
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
    SSM_PREFIX = "/topal/${var.env}"
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
  timeout       = 5 # Teams 5秒タイムアウトに合わせる

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = merge(local.lambda_common_env, {
      TASK_QUEUE_URL = aws_sqs_queue.task_queue.url
    })
  }

  tags = { Name = "${local.name_prefix}-teams-webhook" }
}

resource "aws_lambda_function" "slack_webhook" {
  function_name = "${local.name_prefix}-slack-webhook"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/slack_webhook.handler"
  runtime       = "python3.12"
  timeout       = 5 # Slack 3秒タイムアウト + マージン

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = merge(local.lambda_common_env, {
      TASK_QUEUE_URL = aws_sqs_queue.task_queue.url
    })
  }

  tags = { Name = "${local.name_prefix}-slack-webhook" }
}

resource "aws_lambda_function" "task_worker" {
  function_name = "${local.name_prefix}-task-worker"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/task_worker.handler"
  runtime       = "python3.12"
  timeout       = 120

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = local.lambda_common_env
  }

  tags = { Name = "${local.name_prefix}-task-worker" }
}

resource "aws_lambda_function" "report_scheduler" {
  function_name = "${local.name_prefix}-report-scheduler"
  role          = aws_iam_role.lambda.arn
  handler       = "src/handlers/report_scheduler.handler"
  runtime       = "python3.12"
  timeout       = 300 # 複数プロジェクト対応のため余裕を持たせる

  filename         = "${path.module}/../dist/app.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/app.zip")
  layers           = [aws_lambda_layer_version.deps.arn]

  environment {
    variables = merge(local.lambda_common_env, {
      REPORT_PROJECT_KEYS = var.report_project_keys
      TASK_QUEUE_URL      = aws_sqs_queue.task_queue.url
    })
  }

  tags = { Name = "${local.name_prefix}-report-scheduler" }
}

# --- EventBridge → Lambda (日次レポートスケジュール) ---

resource "aws_cloudwatch_event_rule" "daily_report" {
  for_each = var.report_schedules

  name                = "${local.name_prefix}-daily-report-${each.key}"
  description         = "日次レポート (${each.key})"
  schedule_expression = each.value
  is_enabled          = false # 一時的に無効化
}

resource "aws_cloudwatch_event_target" "daily_report" {
  for_each = var.report_schedules

  rule = aws_cloudwatch_event_rule.daily_report[each.key].name
  arn  = aws_lambda_function.report_scheduler.arn
}

resource "aws_lambda_permission" "daily_report" {
  for_each = var.report_schedules

  statement_id  = "AllowEventBridgeInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.report_scheduler.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_report[each.key].arn
}

# --- SQS → Lambda Event Source Mapping ---

resource "aws_lambda_event_source_mapping" "task_worker_sqs" {
  event_source_arn = aws_sqs_queue.task_queue.arn
  function_name    = aws_lambda_function.task_worker.arn
  batch_size       = 1
  enabled          = true
}

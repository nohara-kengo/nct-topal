# --- SSM Parameters ---

# 共通設定
resource "aws_ssm_parameter" "claude_model" {
  name      = "/topal/claude_model"
  type      = "String"
  value     = var.claude_model
  overwrite = true
}

resource "aws_ssm_parameter" "anthropic_api_key" {
  name      = "/topal/anthropic_api_key"
  type      = "SecureString"
  value     = var.anthropic_api_key
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}

# Slack設定
resource "aws_ssm_parameter" "slack_signing_secret" {
  name      = "/topal/slack_signing_secret"
  type      = "SecureString"
  value     = var.slack_signing_secret
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "slack_bot_token" {
  name      = "/topal/slack_bot_token"
  type      = "SecureString"
  value     = var.slack_bot_token
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}

# Teams Bot Framework設定（未設定時はダミー値）
resource "aws_ssm_parameter" "microsoft_app_id" {
  name      = "/topal/microsoft_app_id"
  type      = "String"
  value     = var.microsoft_app_id
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "microsoft_app_password" {
  name      = "/topal/microsoft_app_password"
  type      = "SecureString"
  value     = var.microsoft_app_password
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}

# Backlog（プロジェクトごと）
resource "aws_ssm_parameter" "backlog_api_key" {
  for_each = toset(split(",", var.report_project_keys))

  name      = "/topal/${each.value}/backlog_api_key"
  type      = "SecureString"
  value     = var.backlog_api_keys[each.value]
  overwrite = true

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "backlog_space_url" {
  for_each = toset(split(",", var.report_project_keys))

  name      = "/topal/${each.value}/backlog_space_url"
  type      = "String"
  value     = var.backlog_space_urls[each.value]
  overwrite = true
}

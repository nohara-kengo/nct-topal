# --- SSM Parameters ---
# 初回作成のみ。値の変更はAWSコンソールまたはCLIで行う。
# 新環境構築時: terraform apply → aws ssm put-parameter で実際の値を設定

# --- 既存パラメータのimport（初回apply後に削除してOK） ---
import {
  to = aws_ssm_parameter.claude_model
  id = "/topal/claude_model"
}
import {
  to = aws_ssm_parameter.anthropic_api_key
  id = "/topal/anthropic_api_key"
}
import {
  to = aws_ssm_parameter.slack_signing_secret
  id = "/topal/slack_signing_secret"
}
import {
  to = aws_ssm_parameter.slack_bot_token
  id = "/topal/slack_bot_token"
}
import {
  to = aws_ssm_parameter.microsoft_app_id
  id = "/topal/microsoft_app_id"
}
import {
  to = aws_ssm_parameter.microsoft_app_password
  id = "/topal/microsoft_app_password"
}
import {
  to = aws_ssm_parameter.backlog_api_key["NOHARATEST"]
  id = "/topal/NOHARATEST/backlog_api_key"
}
import {
  to = aws_ssm_parameter.backlog_space_url["NOHARATEST"]
  id = "/topal/NOHARATEST/backlog_space_url"
}

# 共通設定
resource "aws_ssm_parameter" "claude_model" {
  name  = "/topal/claude_model"
  type  = "String"
  value = var.claude_model

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "anthropic_api_key" {
  name  = "/topal/anthropic_api_key"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# Slack設定
resource "aws_ssm_parameter" "slack_signing_secret" {
  name  = "/topal/slack_signing_secret"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "slack_bot_token" {
  name  = "/topal/slack_bot_token"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# Teams Bot Framework設定
resource "aws_ssm_parameter" "microsoft_app_id" {
  name  = "/topal/microsoft_app_id"
  type  = "String"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "microsoft_app_password" {
  name  = "/topal/microsoft_app_password"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# Backlog（プロジェクトごと）
resource "aws_ssm_parameter" "backlog_api_key" {
  for_each = toset(split(",", var.report_project_keys))

  name  = "/topal/${each.value}/backlog_api_key"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# チャネル→プロジェクトキーマッピング
resource "aws_ssm_parameter" "channel_mapping" {
  for_each = var.channel_project_mappings

  name  = "/topal/channel_mappings/${each.key}"
  type  = "String"
  value = each.value
}

resource "aws_ssm_parameter" "backlog_space_url" {
  for_each = toset(split(",", var.report_project_keys))

  name  = "/topal/${each.value}/backlog_space_url"
  type  = "String"
  value = var.backlog_space_urls[each.value]

  lifecycle {
    ignore_changes = [value]
  }
}

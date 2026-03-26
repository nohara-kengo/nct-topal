# --- SSM Parameters ---
# 初回作成のみ。値の変更はAWSコンソールまたはCLIで行う。
# 新環境構築時: terraform apply → aws ssm put-parameter で実際の値を設定
# パスは /topal/{env}/... で環境ごとに分離される

# 共通設定
resource "aws_ssm_parameter" "claude_model" {
  name  = "/topal/${var.env}/claude_model"
  type  = "String"
  value = var.claude_model

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "anthropic_api_key" {
  name  = "/topal/${var.env}/anthropic_api_key"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# Slack設定
resource "aws_ssm_parameter" "slack_signing_secret" {
  name  = "/topal/${var.env}/slack_signing_secret"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "slack_bot_token" {
  name  = "/topal/${var.env}/slack_bot_token"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# Teams Bot Framework設定
resource "aws_ssm_parameter" "microsoft_app_id" {
  name  = "/topal/${var.env}/microsoft_app_id"
  type  = "String"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "microsoft_app_password" {
  name  = "/topal/${var.env}/microsoft_app_password"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# Backlog（プロジェクトごと）
resource "aws_ssm_parameter" "backlog_api_key" {
  for_each = toset(split(",", var.report_project_keys))

  name  = "/topal/${var.env}/${each.value}/backlog_api_key"
  type  = "SecureString"
  value = "CHANGE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# チャネル→プロジェクトキーマッピング
resource "aws_ssm_parameter" "channel_mapping" {
  for_each = var.channel_project_mappings

  name  = "/topal/${var.env}/channel_mappings/${each.key}"
  type  = "String"
  value = each.value
}

resource "aws_ssm_parameter" "backlog_space_url" {
  for_each = toset(split(",", var.report_project_keys))

  name  = "/topal/${var.env}/${each.value}/backlog_space_url"
  type  = "String"
  value = var.backlog_space_urls[each.value]

  lifecycle {
    ignore_changes = [value]
  }
}

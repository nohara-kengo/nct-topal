# --- SSM Parameters ---
# シークレットはGitHub Actions Secretsから TF_VAR_xxx 経由で渡される
# パスは /topal/{env}/... で環境ごとに分離

# 共通設定
resource "aws_ssm_parameter" "claude_model" {
  name  = "/topal/${var.env}/claude_model"
  type  = "String"
  value = var.claude_model
}

resource "aws_ssm_parameter" "anthropic_api_key" {
  name  = "/topal/${var.env}/anthropic_api_key"
  type  = "SecureString"
  value = var.anthropic_api_key
}

# Slack設定
resource "aws_ssm_parameter" "slack_signing_secret" {
  name  = "/topal/${var.env}/slack_signing_secret"
  type  = "SecureString"
  value = var.slack_signing_secret
}

resource "aws_ssm_parameter" "slack_bot_token" {
  name  = "/topal/${var.env}/slack_bot_token"
  type  = "SecureString"
  value = var.slack_bot_token
}

# Teams Bot Framework設定
resource "aws_ssm_parameter" "microsoft_app_id" {
  name  = "/topal/${var.env}/microsoft_app_id"
  type  = "String"
  value = var.microsoft_app_id
}

resource "aws_ssm_parameter" "microsoft_app_password" {
  name  = "/topal/${var.env}/microsoft_app_password"
  type  = "SecureString"
  value = var.microsoft_app_password
}

# Backlog（プロジェクトごと）
resource "aws_ssm_parameter" "backlog_api_key" {
  for_each = var.backlog_api_keys

  name  = "/topal/${var.env}/${each.key}/backlog_api_key"
  type  = "SecureString"
  value = each.value
}

# チャネル→プロジェクトキーマッピング
resource "aws_ssm_parameter" "channel_mapping" {
  for_each = var.channel_project_mappings

  name  = "/topal/${var.env}/channel_mappings/${each.key}"
  type  = "String"
  value = each.value
}

resource "aws_ssm_parameter" "backlog_space_url" {
  for_each = var.backlog_space_urls

  name  = "/topal/${var.env}/${each.key}/backlog_space_url"
  type  = "String"
  value = each.value
}

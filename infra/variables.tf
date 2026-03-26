variable "aws_region" {
  type    = string
  default = "ap-northeast-1"
}

variable "project" {
  type    = string
  default = "topal"
}

variable "env" {
  type    = string
  default = "dev"
}

variable "report_project_keys" {
  description = "日次レポート対象のBacklogプロジェクトキー（カンマ区切り）"
  type        = string
  default     = "NOHARATEST"
}

# --- SSM パラメータ（シークレット） ---
# 値はS3の secrets/{env}.secrets.tfvars から渡される

variable "anthropic_api_key" {
  description = "Anthropic APIキー"
  type        = string
  sensitive   = true
}

variable "slack_signing_secret" {
  description = "Slack Signing Secret"
  type        = string
  sensitive   = true
}

variable "slack_bot_token" {
  description = "Slack Bot Token"
  type        = string
  sensitive   = true
}

variable "microsoft_app_id" {
  description = "Azure AD アプリケーションID"
  type        = string
}

variable "microsoft_app_password" {
  description = "Azure AD クライアントシークレット"
  type        = string
  sensitive   = true
}

variable "backlog_api_keys" {
  description = "プロジェクトキー→Backlog APIキーのマップ"
  type        = map(string)
  sensitive   = true
}

variable "claude_model" {
  description = "Claude APIのモデル名"
  type        = string
  default     = "claude-haiku-4-5-20251001"
}

variable "backlog_space_urls" {
  description = "プロジェクトキー→BacklogスペースURLのマップ"
  type        = map(string)
  default = {
    NOHARATEST = "https://comthink06.backlog.com"
  }
}

variable "channel_project_mappings" {
  description = "チャネルID→Backlogプロジェクトキーのマッピング"
  type        = map(string)
  default     = {}
}

variable "report_schedules" {
  description = "日次レポートのcronスケジュール（UTC）名前→cron式のマップ"
  type        = map(string)
  default = {
    morning   = "cron(0 23 ? * SUN-THU *)" # JST 8:00 平日
    afternoon = "cron(0 6 ? * MON-FRI *)"  # JST 15:00 平日
  }
}

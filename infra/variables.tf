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

# --- SSM パラメータ値 ---

variable "claude_model" {
  description = "Claude APIのモデル名"
  type        = string
  default     = "claude-haiku-4-5-20251001"
}

variable "anthropic_api_key" {
  description = "Anthropic APIキー（初回のみ。以降はignore_changes）"
  type        = string
  default     = "dummy"
  sensitive   = true
}

variable "slack_signing_secret" {
  description = "Slack Signing Secret（初回のみ）"
  type        = string
  default     = "dummy"
  sensitive   = true
}

variable "slack_bot_token" {
  description = "Slack Bot Token（初回のみ）"
  type        = string
  default     = "dummy"
  sensitive   = true
}

variable "microsoft_app_id" {
  description = "Azure AD アプリケーションID（未設定時はダミー）"
  type        = string
  default     = "dummy-app-id"
}

variable "microsoft_app_password" {
  description = "Azure AD クライアントシークレット（未設定時はダミー）"
  type        = string
  default     = "dummy"
  sensitive   = true
}

variable "backlog_api_keys" {
  description = "プロジェクトキー→Backlog APIキーのマップ（初回のみ）"
  type        = map(string)
  default = {
    NOHARATEST = "dummy"
  }
  sensitive = true
}

variable "backlog_space_urls" {
  description = "プロジェクトキー→BacklogスペースURLのマップ"
  type        = map(string)
  default = {
    NOHARATEST = "https://comthink06.backlog.com"
  }
}

variable "report_schedules" {
  description = "日次レポートのcronスケジュール（UTC）名前→cron式のマップ"
  type        = map(string)
  default = {
    morning   = "cron(0 23 ? * SUN-THU *)" # JST 8:00 平日
    afternoon = "cron(0 6 ? * MON-FRI *)"  # JST 15:00 平日
  }
}

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

# --- SSM パラメータ（Terraformで管理するのはキーの存在のみ、値はCLIで設定） ---

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

variable "report_schedules" {
  description = "日次レポートのcronスケジュール（UTC）名前→cron式のマップ"
  type        = map(string)
  default = {
    morning   = "cron(0 23 ? * SUN-THU *)" # JST 8:00 平日
    afternoon = "cron(0 6 ? * MON-FRI *)"  # JST 15:00 平日
  }
}

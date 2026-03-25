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

variable "report_schedules" {
  description = "日次レポートのcronスケジュール（UTC）名前→cron式のマップ"
  type        = map(string)
  default = {
    morning   = "cron(0 23 ? * SUN-THU *)" # JST 8:00 平日
    afternoon = "cron(0 6 ? * MON-FRI *)"  # JST 15:00 平日
  }
}

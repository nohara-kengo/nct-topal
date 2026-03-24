# --- SQS: タスク処理キュー ---

resource "aws_sqs_queue" "task_dlq" {
  name                      = "${local.name_prefix}-task-dlq"
  message_retention_seconds = 1209600 # 14日

  tags = { Name = "${local.name_prefix}-task-dlq" }
}

resource "aws_sqs_queue" "task_queue" {
  name                       = "${local.name_prefix}-task-queue"
  visibility_timeout_seconds = 300   # worker Lambda timeout(120s) × 2 + マージン
  message_retention_seconds  = 86400 # 1日

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.task_dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${local.name_prefix}-task-queue" }
}

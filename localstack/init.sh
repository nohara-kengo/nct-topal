#!/bin/bash
# LocalStack起動時に実行される初期化スクリプト
# シークレットは環境変数から読み込む（.env.local で設定）

REGION=ap-northeast-1

echo "=== SSM Parameters ==="

# 共通設定
awslocal ssm put-parameter \
  --name "/topal/anthropic_api_key" \
  --value "${ANTHROPIC_API_KEY:-YOUR_ANTHROPIC_API_KEY}" \
  --type SecureString \
  --overwrite \
  --region $REGION

awslocal ssm put-parameter \
  --name "/topal/claude_model" \
  --value "claude-haiku-4-5-20251001" \
  --type String \
  --overwrite \
  --region $REGION

awslocal ssm put-parameter \
  --name "/topal/teams_webhook_secret" \
  --value "${TEAMS_WEBHOOK_SECRET:-YOUR_TEAMS_WEBHOOK_SECRET}" \
  --type SecureString \
  --overwrite \
  --region $REGION

# Backlog（プロジェクトごと）
awslocal ssm put-parameter \
  --name "/topal/NOHARATEST/backlog_api_key" \
  --value "r5jVhoYIvU9yPIyt5rppwU6MwiXxCfI30Wl7JOvkeddEEhacwkX6m1JXYnP9zTiP" \
  --type SecureString \
  --overwrite \
  --region $REGION

# NOTE: --valueにURLを渡すとawslocalがリモートパスとして解釈するため--cli-input-jsonを使う
awslocal ssm put-parameter \
  --cli-input-json '{"Name":"/topal/NOHARATEST/backlog_space_url","Value":"https://comthink06.backlog.com","Type":"String","Overwrite":true}' \
  --region $REGION

echo "=== SQS Queues ==="

# Teams Webhook非同期処理用キュー
awslocal sqs create-queue \
  --queue-name topal-task-queue \
  --region $REGION

# デッドレターキュー
awslocal sqs create-queue \
  --queue-name topal-task-queue-dlq \
  --region $REGION

echo "=== Init complete ==="

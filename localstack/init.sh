#!/bin/bash
# LocalStack起動時に実行される初期化スクリプト
# シークレットは環境変数から読み込む（.env.local で設定）

REGION=ap-northeast-1
ENV=${TOPAL_ENV:-dev}
PREFIX="topal-${ENV}"
SSM_PREFIX="/topal/${ENV}"

echo "=== SSM Parameters (env=${ENV}, prefix=${SSM_PREFIX}) ==="

# 共通設定
awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/anthropic_api_key" \
  --value "${ANTHROPIC_API_KEY:-YOUR_ANTHROPIC_API_KEY}" \
  --type SecureString \
  --overwrite \
  --region $REGION

awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/claude_model" \
  --value "claude-haiku-4-5-20251001" \
  --type String \
  --overwrite \
  --region $REGION

awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/microsoft_app_id" \
  --value "${MICROSOFT_APP_ID:-dummy-app-id}" \
  --type String \
  --overwrite \
  --region $REGION

awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/microsoft_app_password" \
  --value "${MICROSOFT_APP_PASSWORD:-dummy-app-password}" \
  --type SecureString \
  --overwrite \
  --region $REGION

# Backlog（プロジェクトごと）
awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/NOHARATEST/backlog_api_key" \
  --value "r5jVhoYIvU9yPIyt5rppwU6MwiXxCfI30Wl7JOvkeddEEhacwkX6m1JXYnP9zTiP" \
  --type SecureString \
  --overwrite \
  --region $REGION

# NOTE: --valueにURLを渡すとawslocalがリモートパスとして解釈するため--cli-input-jsonを使う
awslocal ssm put-parameter \
  --cli-input-json "{\"Name\":\"${SSM_PREFIX}/NOHARATEST/backlog_space_url\",\"Value\":\"https://comthink06.backlog.com\",\"Type\":\"String\",\"Overwrite\":true}" \
  --region $REGION

# Slack設定
awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/slack_signing_secret" \
  --value "${SLACK_SIGNING_SECRET:-dummy-signing-secret}" \
  --type SecureString \
  --overwrite \
  --region $REGION

awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/slack_bot_token" \
  --value "${SLACK_BOT_TOKEN:-xoxb-dummy-token}" \
  --type SecureString \
  --overwrite \
  --region $REGION

# チャネル→プロジェクトキーマッピング
awslocal ssm put-parameter \
  --name "${SSM_PREFIX}/channel_mappings/C0AP3RM59B3" \
  --value "NOHARATEST" \
  --type String \
  --overwrite \
  --region $REGION

echo "=== SQS Queues (prefix=${PREFIX}) ==="

# Teams Webhook非同期処理用キュー
awslocal sqs create-queue \
  --queue-name "${PREFIX}-task-queue" \
  --region $REGION

# デッドレターキュー
awslocal sqs create-queue \
  --queue-name "${PREFIX}-task-queue-dlq" \
  --region $REGION

echo "=== Init complete (env=${ENV}) ==="

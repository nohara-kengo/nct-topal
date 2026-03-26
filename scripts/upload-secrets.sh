#!/bin/bash
# .env.local の値メモから secrets.tfvars を生成して S3 にアップロードする
# Usage: ./scripts/upload-secrets.sh [dev|prd]

set -euo pipefail

ENV="${1:-dev}"
BUCKET="topal-tfstate-265123441862"
S3_KEY="secrets/${ENV}.secrets.tfvars"
ENV_LOCAL=".env.local"
OUTPUT="infra/envs/${ENV}.secrets.tfvars"

if [ ! -f "$ENV_LOCAL" ]; then
  echo "ERROR: $ENV_LOCAL が見つかりません" >&2
  exit 1
fi

# .env.local の「現在の値メモ」セクションから値を抽出する関数
extract_value() {
  local key="$1"
  grep "^# ${key}" "$ENV_LOCAL" | head -1 | sed 's/^# [^=]*= *//'
}

ANTHROPIC_API_KEY=$(extract_value "ANTHROPIC_API_KEY")
SLACK_SIGNING_SECRET=$(extract_value "SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN=$(extract_value "SLACK_BOT_TOKEN")
MICROSOFT_APP_ID=$(extract_value "MICROSOFT_APP_ID")
MICROSOFT_APP_PASSWORD=$(extract_value "MICROSOFT_APP_PASSWORD")

# Backlog API キーをマップ形式で抽出
BACKLOG_KEYS=""
while IFS= read -r line; do
  proj=$(echo "$line" | sed -n 's/^# BACKLOG_API_KEY(\([^)]*\)).*/\1/p')
  val=$(echo "$line" | sed 's/^# [^=]*= *//')
  if [ -n "$proj" ] && [ -n "$val" ]; then
    BACKLOG_KEYS="${BACKLOG_KEYS}  ${proj} = \"${val}\"\n"
  fi
done < <(grep "^# BACKLOG_API_KEY(" "$ENV_LOCAL")

# 必須チェック（Teams系は未設定でもdummyで通す）
missing=""
[ -z "$ANTHROPIC_API_KEY" ] && missing="${missing} ANTHROPIC_API_KEY"
[ -z "$SLACK_SIGNING_SECRET" ] && missing="${missing} SLACK_SIGNING_SECRET"
[ -z "$SLACK_BOT_TOKEN" ] && missing="${missing} SLACK_BOT_TOKEN"
[ -z "$BACKLOG_KEYS" ] && missing="${missing} BACKLOG_API_KEY"

if [ -n "$missing" ]; then
  echo "ERROR: .env.local に以下の値が未設定です:${missing}" >&2
  echo "「現在の値メモ」セクションに値を追加してください" >&2
  exit 1
fi

# Teams系は未設定なら空文字で生成（Teams連携不要時）
MICROSOFT_APP_ID="${MICROSOFT_APP_ID:-}"
MICROSOFT_APP_PASSWORD="${MICROSOFT_APP_PASSWORD:-}"

# tfvars ファイル生成
cat > "$OUTPUT" <<EOF
# ${ENV}環境のシークレット（自動生成 — $(date +%Y-%m-%d)）
# 生成元: .env.local → scripts/upload-secrets.sh

anthropic_api_key      = "${ANTHROPIC_API_KEY}"
slack_signing_secret   = "${SLACK_SIGNING_SECRET}"
slack_bot_token        = "${SLACK_BOT_TOKEN}"
microsoft_app_id       = "${MICROSOFT_APP_ID}"
microsoft_app_password = "${MICROSOFT_APP_PASSWORD}"

backlog_api_keys = {
$(echo -e "$BACKLOG_KEYS")}
EOF

echo "生成: $OUTPUT"

# S3 アップロード
echo "アップロード: s3://${BUCKET}/${S3_KEY}"
aws s3 cp "$OUTPUT" "s3://${BUCKET}/${S3_KEY}"

echo "完了: ${ENV} secrets を S3 にアップロードしました"

# ローカルの secrets.tfvars は gitignore されているが念のため削除
rm -f "$OUTPUT"
echo "クリーンアップ: $OUTPUT を削除しました"

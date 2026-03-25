# Slack連携機能 実装プラン

## 概要
Slack App（Event API `app_mention`）からもタスク起票できるようにする。
既存のTeams実装は変更せず、Slack固有層を新規追加する。

## 方針
- 汎用層（intent_classifier, issue_generator, backlog_client, task_create/update）はそのまま流用
- SQSキューは共有し、メッセージに `platform` フィールドを追加して通知先を振り分け
- Slack SDK不要（`requests` で Slack Web API を直接呼ぶ）
- `requirements.txt` の追加依存なし

## 実装ステップ

各ステップは独立して着手可能（Step 1〜4 は並行可、Step 5 は 1〜4 に依存）。

### Step 1: SSMパラメータ追加 ✅ 完了
- [x] `src/services/ssm_client.py` に `get_slack_signing_secret()`, `get_slack_bot_token()` 追加
- [x] `tests/test_ssm_client.py` にテスト追加

### Step 2: Slack署名検証 ✅ 完了
- [x] `src/services/slack_auth.py` 新規作成
  - `validate_request(headers, body) -> bool`
  - HMAC-SHA256署名検証、タイムスタンプ5分制限（リプレイ攻撃対策）
- [x] `tests/test_slack_auth.py` 新規作成

### Step 3: Slackメッセージパーサー ✅ 完了
- [x] `src/services/slack_message_parser.py` 新規作成
  - `strip_mentions(text)` — `<@U...>` 除去
  - `extract_text(payload)` — Event APIペイロードからテキスト抽出
- [x] `tests/test_slack_message_parser.py` 新規作成

### Step 4: Slack応答送信 ✅ 完了
- [x] `src/services/slack_response.py` 新規作成
  - `post_message(channel, text, thread_ts=None)` — `chat.postMessage` で送信
- [x] `tests/test_slack_response.py` 新規作成

### Step 5: Slack Webhookハンドラー ✅ 完了
- [x] `src/handlers/slack_webhook.py` 新規作成
  - 署名検証 → url_verification対応 → app_mention処理 → SQS投入（即200返却）
  - SQS未設定時は同期フォールバック
- [x] `tests/test_slack_webhook.py` 新規作成

### Step 6: task_worker のplatform対応 ✅ 完了
- [x] `src/handlers/task_worker.py` の `_notify` と `_process_record` を変更
  - `platform == "slack"` → `slack_response.post_message`
  - `platform == "teams"` → 既存の `teams_notifier.notify`（変更なし）

### Step 7: インフラ（Terraform） ✅ 完了
- [x] `infra/lambda.tf` — `slack_webhook` Lambda関数追加
- [x] `infra/api_gateway.tf` — `POST /webhook/slack` ルート追加
- [x] `localstack/init.sh` — Slack用SSMパラメータ追加
- [x] `.github/workflows/deploy.yml` — Lambda検証リストに `slack-webhook` 追加

### Step 8: E2Eテスト ✅ 完了
- [x] `tests/test_e2e_slack_webhook.py` 新規作成（Claude API実呼び出し）

## 変更対象ファイル

### 新規作成（9ファイル）
| ファイル | 責務 |
|---------|------|
| `src/services/slack_auth.py` | Signing Secret署名検証 |
| `src/services/slack_message_parser.py` | メンション除去・テキスト抽出 |
| `src/services/slack_response.py` | Slack Web API `chat.postMessage` |
| `src/handlers/slack_webhook.py` | Event API Webhookハンドラー |
| `tests/test_slack_auth.py` | slack_auth単体テスト |
| `tests/test_slack_message_parser.py` | パーサー単体テスト |
| `tests/test_slack_response.py` | 応答送信単体テスト |
| `tests/test_slack_webhook.py` | ハンドラー単体テスト |
| `tests/test_e2e_slack_webhook.py` | E2Eテスト |

### 既存変更（6ファイル）
| ファイル | 変更内容 |
|---------|---------|
| `src/services/ssm_client.py` | Slack用パラメータ取得関数2つ追加 |
| `src/handlers/task_worker.py` | `_notify` のplatform振り分け |
| `infra/lambda.tf` | `slack_webhook` Lambda追加 |
| `infra/api_gateway.tf` | `POST /webhook/slack` ルート追加 |
| `localstack/init.sh` | Slack用SSMパラメータ追加 |
| `.github/workflows/deploy.yml` | Lambda検証リスト更新 |

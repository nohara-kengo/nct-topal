# ToPal 開発進捗・残件レポート

最終更新: 2026-03-24

---

## 1. プロジェクト概要

Teams のメンションメッセージから Backlog の課題を自動起票・更新するサービス。
Claude API で意図判定と課題内容生成を行い、Backlog API で課題を操作する。

### アーキテクチャ（処理フロー）

```
[Teams チャネル]
  │
  │ Outgoing Webhook（メンション時に発火）
  ↓
[Lambda A: teams_webhook]（受付専用・軽量・5秒以内）
  → HMAC署名検証
  → メッセージ解析（message_parser）
  → SQS にメッセージをキューイング
  → 即座に「処理中です...しばらくお待ちください。」を返却
  │
  ↓
[SQS: topal-task-queue]
  │  ※失敗時 → topal-task-queue-dlq（デッドレターキュー、最大3回リトライ）
  ↓
[Lambda B: task_worker]（SQSトリガー・非同期処理・120秒）
  → intent_classifier（Claude API 1回目: 意図判定、リトライ付き）
  → SSMからプロジェクト設定取得
  → [create] issue_generator（Claude API 2回目: 課題内容生成、リトライ付き）
           → task_create（Backlog API、レート制限リトライ付き）
  → [update] task_update（Backlog API、レート制限リトライ付き）
  → 結果を Teams Incoming Webhook URL に POST（Adaptive Card形式）
  │
  ↓
[Teams チャネル]
  ← 「✅ 野原 太郎さんのリクエストでタスクを作成しました: NOHARATEST-1 ログイン機能を実装する。」
```

※ `TASK_QUEUE_URL` 環境変数が未設定の場合は同期処理にフォールバック（開発・テスト用）

---

## 2. ファイル構成と各モジュールの役割

### ハンドラー (`src/handlers/`)

| ファイル | 役割 | API/トリガー |
|---|---|---|
| `health.py` | ヘルスチェック | `GET /health` |
| `teams_webhook.py` | Teams Webhook受信・SQSキューイング・即時応答 | `POST /webhook/teams` |
| `task_worker.py` | SQSメッセージ処理・Claude API・Backlog API・Incoming Webhook通知 | SQS → Lambda |
| `task_create.py` | タスク新規作成 | `POST /tasks` |
| `task_update.py` | タスク更新 | `PUT /tasks/{taskId}` |
| `project_setup.py` | プロジェクト初期設定（種別・カテゴリ・ステータス・テンプレート） | `POST /projects/{projectKey}/setup` |

### サービス (`src/services/`)

| ファイル | 役割 | 外部依存 |
|---|---|---|
| `ssm_client.py` | AWS SSM Parameter Storeからシークレット・設定値取得（キャッシュ付き） | AWS SSM (LocalStack) |
| `hmac_validator.py` | Teams Outgoing WebhookのHMAC-SHA256署名検証 | SSM経由でシークレット取得 |
| `message_parser.py` | メンションタグ除去・テキスト抽出 | なし |
| `intent_classifier.py` | 1回目のClaude API呼び出し。意図判定（リトライ付き） | Claude API |
| `issue_generator.py` | 2回目のClaude API呼び出し。課題の種別・題名・説明・予定時間を生成（リトライ付き） | Claude API |
| `backlog_client.py` | Backlog REST API通信（レート制限429リトライ付き） | Backlog API |
| `backlog_setup.py` | プロジェクト初期設定ロジック（種別・カテゴリ・ステータス確保、テンプレート設定、スケジュール計算） | backlog_client経由 |
| `assignee_resolver.py` | 担当者名からBacklogユーザーIDを解決（完全一致→部分一致のあいまい検索） | backlog_client経由 |
| `teams_response.py` | Teams Outgoing Webhook向けレスポンス生成 | なし |
| `teams_notifier.py` | Teams Incoming Webhookで結果通知（Adaptive Card形式） | Teams Incoming Webhook |
| `log_config.py` | CloudWatch向けJSON構造化ログ設定 | なし |

### テンプレート (`src/templates/`)

| ファイル | 役割 |
|---|---|
| `issue_type_templates.json` | 14種の課題種別テンプレート（Backlog設定とClaude プロンプト入力の両方で使用） |

### テスト (`tests/`)

| ファイル | テスト数 | 対象 |
|---|---|---|
| `test_assignee_resolver.py` | 8 | 担当者あいまい検索（完全一致/部分一致/全角スペース/複数一致） |
| `test_backlog_setup.py` | 29 | 種別・カテゴリ・ステータス確保、テンプレート、スケジュール計算 |
| `test_e2e_teams_webhook.py` | 6 (4スキップ) | E2E結合テスト（Claude API実呼び出し、Backlogモック） |
| `test_health.py` | 1 | ヘルスチェック |
| `test_hmac_validator.py` | 6 | HMAC署名検証 |
| `test_intent_classifier.py` | 6 | 意図判定（モック）、フィールド緩和テスト含む |
| `test_issue_generator.py` | 4 | 課題生成（モック） |
| `test_message_parser.py` | 7 | メンションタグ除去 |
| `test_project_setup.py` | 4 | プロジェクト初期設定ハンドラー |
| `test_ssm_client.py` | 4 (4スキップ) | SSMクライアント（LocalStack依存） |
| `test_task_create.py` | 4 | タスク新規作成 |
| `test_task_update.py` | 2 | タスク更新 |
| `test_task_worker.py` | 3 | SQSワーカー（作成/更新/project_key無し） |
| `test_teams_webhook.py` | 8 | Webhook受信・振り分け（モック） |
| **合計** | **92 (82 pass, 4 skip, 6 E2E skip)** | |

### インフラ (`infra/`)

| ファイル | 役割 |
|---|---|
| `main.tf` | Terraform設定、S3バックエンド、AWSプロバイダー |
| `lambda.tf` | IAMロール、Lambda Layer、6つのLambda関数、SQS権限、イベントソースマッピング |
| `api_gateway.tf` | HTTP API Gateway（4ルート） |
| `sqs.tf` | SQSキュー（task-queue + task-dlq） |
| `variables.tf` | 変数定義（region, project, env） |
| `outputs.tf` | 出力（api_url, task_queue_url, task_dlq_url） |

---

## 3. 完了済みの作業

### Phase 1 基盤

- [x] Docker Compose開発環境構築（app + LocalStack）
- [x] LocalStack SSMパラメータ初期化スクリプト
- [x] AWS SSM Parameter Storeクライアント（キャッシュ付き）
- [x] Terraform基盤定義ファイル（Lambda, API Gateway, SQS）
- [x] 実AWSデプロイ（Lambda 6つ + API Gateway + IAM + Layer）
- [x] S3バックエンドへのterraform state移行
- [x] GitHub Actions CI/CD（ci.yml + deploy.yml）
- [x] GitHub Secrets設定（AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY）
- [x] requirements.txt分離（本番用 / dev用）

### Teams Webhook受信

- [x] HMAC-SHA256署名検証（`hmac_validator`）
- [x] メンションタグ除去・HTMLタグ除去（`message_parser`）
- [x] Teams形式レスポンス生成（`teams_response`）
- [x] Webhookハンドラーの振り分けロジック（create/update）
- [x] **Teams 5秒タイムアウト対策（SQS非同期処理）**
  - teams_webhook → SQS送信 → 即時「処理中」応答
  - task_worker → SQSトリガー → Claude API + Backlog API → Incoming Webhook通知
  - TASK_QUEUE_URL未設定時は同期フォールバック（テスト互換性維持）

### Claude API連携（2段階呼び出し）

- [x] **1回目: 意図判定** (`intent_classifier`)
  - action（create/update）判定
  - project_key抽出（`[XXX]`パターン、課題キーのハイフン前）
  - task_id抽出（`XXX-123`パターン）
  - title（20文字以内要約）— 必須
  - priority（高/中/低）— デフォルト"中"にフォールバック
  - estimated_hours — null許容（後段で補完）
  - assignee — null許容
  - **リトライ機構（最大2回、指数バックオフ、RateLimitError/APIStatusError対応）**

- [x] **2回目: 課題内容生成** (`issue_generator`)
  - issue_type: 14種別テンプレートから最適なものを選定
  - title: 動詞完結形（「〜する。」）で30文字以内
  - description: 種別テンプレートの構造に従い、目的/概要/詳細/完了条件を記載
  - estimated_hours: タスク複雑さから概算（0.5h単位、1日=8.5h換算）
  - **リトライ機構（最大2回、指数バックオフ）**

### Backlog連携

- [x] Backlog REST APIクライアント（`backlog_client`）
  - **全メソッドにレート制限（429）リトライ対応（Retry-Afterヘッダー準拠）**
  - プロジェクト情報取得
  - プロジェクトメンバー一覧取得
  - 種別 CRUD + テンプレート設定
  - カテゴリ CRUD
  - ステータス CRUD
  - 課題 作成/更新
- [x] **担当者あいまい検索** (`assignee_resolver`)
  - 完全一致（name, userId） → 部分一致（姓/名/userId含む） の順で検索
  - 全角スペース正規化対応
  - 複数一致時は先頭を使用（警告ログ出力）
  - task_create / task_update の重複ロジックを共通化
- [x] **タスク新規作成** (`task_create`)
- [x] **タスク更新** (`task_update`)

### プロジェクト初期設定 (`project_setup`)

- [x] 13種別の自動作成
- [x] 14種別テンプレート設定（JSON外部ファイルから読み込み、常に上書き）
- [x] 5カスタムステータス作成（AI下書き/遅延-処理中/処理待/レビュー:待/レビュー:済）
- [x] ステータス上限チェック（max 12）
- [x] 「AI生成」カテゴリ作成

### 非機能要件

- [x] **構造化ログ（CloudWatch対応）**
  - Lambda環境ではJSON構造化ログ出力（`log_config.py`）
  - ローカルは通常テキスト形式
  - コンテキスト情報対応（project_key, action, sender_name, issue_key, task_id）
- [x] **エラーハンドリング充実**
  - Claude API: RateLimitError/APIStatusError時にリトライ（最大2回、指数バックオフ）
  - Backlog API: 429レート制限時にリトライ（Retry-Afterヘッダー準拠）
- [x] **E2Eテスト整備**
  - Claude API実呼び出し + Backlogモックの構成
  - SSMパッチ（環境変数からAPI key/model取得）

---

## 4. SSMパラメータ構成

```
/topal/
  anthropic_api_key              # Anthropic APIキー (SecureString) ✅ 設定済み
  claude_model                   # Claudeモデル名 (String)          ✅ 設定済み
  teams_webhook_secret           # Teams Outgoing Webhookシークレット (SecureString) ❌ 未設定
  teams_incoming_webhook_url     # Teams Incoming Webhook URL (String)              ❌ 未設定
  {PROJECT_KEY}/
    backlog_api_key              # Backlog APIキー (SecureString)   ❌ 未設定
    backlog_space_url            # BacklogスペースURL (String)      ❌ 未設定
```

---

## 5. 残件・TODO

### 外部調整待ち（人の作業が必要）

| # | 内容 | 状態 | 次のアクション |
|---|------|------|---------------|
| A | IT管理部にTeams Outgoing Webhook + Incoming Webhook の利用許可確認 | 問い合わせ文面作成済み・未送信 | 文面を送信する |
| B | Claude API 組織アカウントでのAPIキー発行依頼 | 案内文面作成済み・未送信 | 文面を送信する |
| C | Backlog APIキー・スペースURL の確認 | 未着手 | 対象プロジェクトの管理者に確認 |

### 開発残件

| # | 内容 | 優先度 | 状態 |
|---|------|--------|------|
| 1 | 実Backlog APIでの結合テスト | 高 | ❌ C完了待ち |
| 2 | E2Eテスト実行（Claude API実呼び出し） | 高 | ⏳ ANTHROPIC_API_KEY設定で実行可能 |
| 3 | IAMユーザー分離（個人キー → デプロイ専用ユーザー or OIDC連携） | 中 | ❌ 未着手 |
| 4 | Slack対応（フェーズ2） | 低 | ❌ 未着手 |

### 完了済み（今回の実装で解決）

| # | 内容 | 完了日 |
|---|------|--------|
| ~~5~~ | ~~intent_classifier必須フィールド緩和~~ | 2026-03-24 |
| ~~6~~ | ~~担当者あいまい検索~~ | 2026-03-24 |
| ~~7~~ | ~~Teams 5秒タイムアウト対策: Lambda分離 + SQS + Incoming Webhook~~ | 2026-03-24 |
| ~~8~~ | ~~エラーハンドリング充実（Claude APIリトライ、Backlog APIレート制限対応）~~ | 2026-03-24 |
| ~~9~~ | ~~ログ・モニタリング（CloudWatch構造化ログ）~~ | 2026-03-24 |
| ~~10~~ | ~~E2Eテストペイロード修正（SSM/Backlogモック追加）~~ | 2026-03-24 |

---

## 6. 次のアクション

1. **IT管理部への問い合わせ送信**（A）→ Outgoing/Incoming Webhookが使えるか判明
2. **Backlog情報を揃える**（C）→ SSMパラメータ設定 → 結合テスト可能に
3. **Webhook許可が下りたら**:
   - Outgoing Webhook 作成 → secret をSSMに設定
   - Incoming Webhook 作成 → URL をSSMに設定
   - Teamsから疎通確認（E2Eフロー全体）
4. **IAMユーザー分離**（デプロイ専用ユーザー or GitHub OIDC連携）

---

## 7. 技術的な判断ログ

| 判断 | 理由 |
|---|---|
| DB削除 → SSMのみ構成 | プロジェクト設定はSSMで十分。Aurora Serverless v2のコスト・複雑さを排除 |
| Claude API 2段階呼び出し | 1回目（intent_classifier）は軽量・高速に意図判定、2回目（issue_generator）は種別選定・テンプレ記入・時間見積もりの重い処理を分離 |
| テンプレートJSON外部ファイル | Backlog種別テンプレート設定とClaude プロンプト注入の両方で使い回すため |
| テンプレート常に上書き | JSONファイルが正（Single Source of Truth） |
| ステータス上限チェック | Backlog APIの制限（プロジェクト当たり最大12ステータス）に対応 |
| Lambda分離（webhook + worker） | Teams Outgoing Webhookの5秒タイムアウト制約。SQSで非同期化し、Incoming Webhookで結果通知 |
| TASK_QUEUE_URL未設定時の同期フォールバック | テスト・開発時にSQS無しでも既存テストが動作するよう互換性維持 |
| intent_classifier必須フィールド緩和 | estimated_hours/assigneeはユーザーが常に指定するわけではない。null許容にして後段で補完 |
| 担当者あいまい検索 | ユーザーは姓のみで指定することが多い（「野原担当で」→「野原 太郎」にマッチ） |
| Claude APIリトライ（指数バックオフ） | RateLimitError/APIStatusErrorは一時的エラー。2回までリトライで回復率向上 |
| Backlog APIレート制限リトライ | 429レスポンス時にRetry-Afterヘッダーに従ってリトライ |
| JSON構造化ログ（Lambda環境のみ） | CloudWatch Logs Insightsでの検索性向上。ローカルは可読性重視でテキスト形式 |
| QAは「質問」種別 | テスト/品質保証ではなく、特定の誰かに対する質問・確認用途 |
| 予定時間0.5h単位 | Backlogの予定時間入力粒度に合わせた。切り上げ |
| 1日=8.5h | 9:00-17:30の営業時間（休憩なし計算） |

---

## 8. 開発環境情報

```bash
# コンテナ起動
docker compose up -d

# テスト実行
docker exec topal-dev python -m pytest tests/ -v

# コンテナ内にbashで入る
docker exec -it topal-dev bash

# LocalStack SSMパラメータ確認
docker exec topal-localstack awslocal ssm get-parameters-by-path --path /topal --recursive

# 個別パラメータ設定（例: Anthropic APIキー）
docker exec topal-localstack awslocal ssm put-parameter \
  --name "/topal/anthropic_api_key" \
  --value "sk-ant-xxxxx" \
  --type SecureString \
  --overwrite
```

### 依存パッケージ

**本番 (`requirements.txt`)**:
- `anthropic` - Claude API クライアント
- `boto3` - AWS SDK（SSM, SQS）
- `requests` - HTTP通信（Backlog API, Teams Incoming Webhook）

**開発 (`requirements-dev.txt`)**:
- `pytest` - テストフレームワーク
- 上記本番パッケージすべて

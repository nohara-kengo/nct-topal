# ToPal 開発進捗・残件レポート

最終更新: 2026-03-22

---

## 1. プロジェクト概要

Teams のメンションメッセージから Backlog の課題を自動起票・更新するサービス。
Claude API で意図判定と課題内容生成を行い、Backlog API で課題を操作する。

### アーキテクチャ（処理フロー）

```
Teams Outgoing Webhook
  → API Gateway
    → Lambda (teams_webhook handler)
      → HMAC署名検証
      → メンションタグ除去 (message_parser)
      → 1回目 Claude API呼び出し (intent_classifier)
        → action, project_key, task_id, title, priority, estimated_hours, assignee を判定
      → SSMからプロジェクト設定取得 (ssm_client)
      → [create の場合]
        → 2回目 Claude API呼び出し (issue_generator)
          → issue_type, title(動詞完結形), description(テンプレ準拠), estimated_hours を生成
        → task_create handler
          → backlog_setup (カテゴリ・ステータス確保)
          → backlog_client (課題作成)
      → [update の場合]
        → task_update handler
          → backlog_client (課題更新)
      → Teams にレスポンス返却
```

---

## 2. ファイル構成と各モジュールの役割

### ハンドラー (`src/handlers/`)

| ファイル | 役割 | API |
|---|---|---|
| `health.py` | ヘルスチェック | `GET /health` |
| `teams_webhook.py` | Teams Webhook受信・振り分け | `POST /webhook/teams` |
| `task_create.py` | タスク新規作成 | `POST /tasks` |
| `task_update.py` | タスク更新 | `PUT /tasks/{taskId}` |
| `project_setup.py` | プロジェクト初期設定（種別・カテゴリ・ステータス・テンプレート） | `POST /projects/{projectKey}/setup` |

### サービス (`src/services/`)

| ファイル | 役割 | 外部依存 |
|---|---|---|
| `ssm_client.py` | AWS SSM Parameter Storeからシークレット・設定値取得（キャッシュ付き） | AWS SSM (LocalStack) |
| `hmac_validator.py` | Teams Outgoing WebhookのHMAC-SHA256署名検証 | SSM経由でシークレット取得 |
| `message_parser.py` | メンションタグ除去・テキスト抽出 | なし |
| `intent_classifier.py` | 1回目のClaude API呼び出し。意図判定（action/project_key/task_id/title/priority/estimated_hours/assignee） | Claude API |
| `issue_generator.py` | 2回目のClaude API呼び出し。課題の種別・題名・説明・予定時間を生成 | Claude API |
| `backlog_client.py` | Backlog REST API通信（課題CRUD、種別・カテゴリ・ステータス操作、メンバー取得） | Backlog API |
| `backlog_setup.py` | プロジェクト初期設定ロジック（種別・カテゴリ・ステータス確保、テンプレート設定、スケジュール計算） | backlog_client経由 |
| `teams_response.py` | Teams Outgoing Webhook向けレスポンス生成 | なし |

### テンプレート (`src/templates/`)

| ファイル | 役割 |
|---|---|
| `issue_type_templates.json` | 14種の課題種別テンプレート（Backlog設定とClaude プロンプト入力の両方で使用） |

### テスト (`tests/`)

| ファイル | テスト数 | 対象 |
|---|---|---|
| `test_backlog_setup.py` | 29 | 種別・カテゴリ・ステータス確保、テンプレート、スケジュール計算 |
| `test_e2e_teams_webhook.py` | 6 (4スキップ) | E2E結合テスト（Claude API実呼び出し） |
| `test_health.py` | 1 | ヘルスチェック |
| `test_hmac_validator.py` | 6 | HMAC署名検証 |
| `test_intent_classifier.py` | 5 | 意図判定（モック） |
| `test_issue_generator.py` | 4 | 課題生成（モック） |
| `test_message_parser.py` | 7 | メンションタグ除去 |
| `test_project_setup.py` | 4 | プロジェクト初期設定ハンドラー |
| `test_ssm_client.py` | 4 | SSMクライアント |
| `test_task_create.py` | 4 | タスク新規作成 |
| `test_task_update.py` | 2 | タスク更新 |
| `test_teams_webhook.py` | 8 | Webhook受信・振り分け（モック） |
| **合計** | **80 (76 pass, 4 skip)** | |

---

## 3. 完了済みの作業

### Phase 1 基盤

- [x] Docker Compose開発環境構築（app + LocalStack）
- [x] LocalStack SSMパラメータ初期化スクリプト
- [x] AWS SSM Parameter Storeクライアント（キャッシュ付き）
- [x] Terraform基盤定義ファイル（Lambda, API Gateway, VPC, Aurora）

### Teams Webhook受信

- [x] HMAC-SHA256署名検証（`hmac_validator`）
- [x] メンションタグ除去・HTMLタグ除去（`message_parser`）
- [x] Teams形式レスポンス生成（`teams_response`）
- [x] Webhookハンドラーの振り分けロジック（create/update）

### Claude API連携（2段階呼び出し）

- [x] **1回目: 意図判定** (`intent_classifier`)
  - action（create/update）判定
  - project_key抽出（`[XXX]`パターン、課題キーのハイフン前）
  - task_id抽出（`XXX-123`パターン）
  - title（20文字以内要約）
  - priority（高/中/低）
  - estimated_hours（時間数値。半日=4h、1日=8.5h等の換算ルール付き）
  - assignee（担当者名抽出）
  - 必須フィールドバリデーション（task_id以外すべて必須）

- [x] **2回目: 課題内容生成** (`issue_generator`)
  - issue_type: 14種別テンプレートから最適なものを選定
  - title: 動詞完結形（「〜する。」）で30文字以内
  - description: 種別テンプレートの構造に従い、目的/概要/詳細/完了条件を記載
  - estimated_hours: タスク複雑さから概算（0.5h単位、1日=8.5h換算）
  - テンプレートJSON外部ファイルをプロンプトに注入

### Backlog連携

- [x] Backlog REST APIクライアント（`backlog_client`）
  - プロジェクト情報取得
  - プロジェクトメンバー一覧取得
  - 種別 CRUD + テンプレート設定
  - カテゴリ CRUD
  - ステータス CRUD
  - 課題 作成/更新
- [x] **タスク新規作成** (`task_create`)
  - 必須パラメータ: project_key, title, description, issue_type, priority, estimated_hours, assignee
  - 種別名 → 種別ID解決（フォールバック付き）
  - 担当者名 → Backlogユーザー ID解決（プロジェクトメンバーから部分一致検索）
  - 優先度: 高→2, 中→3, 低→4 マッピング
  - カテゴリ「AI生成」自動付与
  - ステータス「AI下書き」で起票
  - スケジュール自動計算（開始日・期限・予定時間）
- [x] **タスク更新** (`task_update`)
  - 必須パラメータ: project_key, priority, estimated_hours, assignee
  - 担当者名 → Backlogユーザー ID解決
  - スケジュール再計算

### プロジェクト初期設定 (`project_setup`)

- [x] 13種別の自動作成（タスク/課題/親タスク/子タスク/親課題/子課題/QA/要求要望/バグ/親スケジュール/スケジュール/情報共有/その他）
- [x] 14種別テンプレート設定（上記13 + 要望。JSON外部ファイルから読み込み、常に上書き）
- [x] 5カスタムステータス作成（AI下書き/遅延-処理中/処理待/レビュー:待/レビュー:済）
- [x] ステータス上限チェック（max 12。超過時は`StatusLimitExceeded`例外 → 409レスポンス）
- [x] 「AI生成」カテゴリ作成

### スケジュール計算 (`backlog_setup.calc_schedule`)

- [x] 現在時刻から本日の残り作業時間を算出（9:00-17:30、8.5h/日）
- [x] 予定時間が本日中に収まるか判定、収まらなければ翌営業日以降に繰り越し
- [x] 土日スキップ（営業日ベース）
- [x] 0.5h単位丸め
- [x] デフォルト8.0h

### テンプレート設計（`issue_type_templates.json`）

- [x] Backlogワークフローガイドラインに準拠
  - 題名: 動詞完結形（「〜する。」）
  - 説明: `# heading\n<!-- comment -->` 形式
  - 目的/概要/詳細/完了条件セクション
  - QA: 質問先/確認事項セクション（テストではなく特定の誰かへの質問）
  - バグ: 再現手順/期待動作/実際の動作/影響範囲セクション
  - 親子リンクセクションなし
  - プレースホルダ（1., - [ ], -）なし
- [x] 対応種別: タスク/課題/親タスク/子タスク/親課題/子課題/QA/要求要望/バグ/親スケジュール/スケジュール/情報共有/その他/要望

### DB削除・SSMのみ構成への移行

- [x] DB関連ファイル削除（database.py, migrator.py, db/ディレクトリ, DBテスト）
- [x] docker-composeからdb, adminerサービス削除
- [x] .envからDB接続情報・Backlog情報・Anthropic情報削除（全てSSMに移行）
- [x] requirements.txtから`psycopg2-binary`削除

---

## 4. SSMパラメータ構成

```
/topal/
  anthropic_api_key          # Anthropic APIキー (SecureString)
  claude_model               # Claudeモデル名 (String) → "claude-sonnet-4-20250514"
  teams_webhook_secret       # Teams Webhookシークレット (SecureString)
  {PROJECT_KEY}/
    backlog_api_key          # Backlog APIキー (SecureString)
    backlog_space_url        # BacklogスペースURL (String) → "https://xxx.backlog.com"
```

---

## 5. 残件・TODO

### 優先度: 高（次にやるべき）

| # | 内容 | 詳細 |
|---|---|---|
| 1 | **結合テスト（Claude API実呼び出し）** | LocalStackのSSMに実際のANTHROPIC_API_KEYを設定し、intent_classifier → issue_generator の2段階Claude呼び出しがE2Eで動作するか検証。Backlog側はモックでOK。`test_e2e_teams_webhook.py` の4テストが現在スキップ中 |
| 2 | **E2Eテストのペイロード更新** | 現在のE2Eテストのペイロードにプロジェクトキー `[NOHARATEST]` が含まれていないものがある。intent_classifierがproject_keyを必須としているため、project_key無しだとValueErrorになる。テストペイロードの修正 or 期待動作の見直しが必要 |
| 3 | **実Backlog APIでの結合テスト** | NOHARATESTプロジェクトに対してproject_setup → task_create のフル結合テスト |

### 優先度: 中（フェーズ1完成に必要）

| # | 内容 | 詳細 |
|---|---|---|
| 4 | **Teams 5秒タイムアウト対策: Lambda分離 + SQS + Incoming Webhook** | 下記「Lambda分離設計」セクション参照 |
| 5 | **Terraformインフラの更新** | `infra/aurora.tf` が残っているがDB削除済み。SSMパラメータ定義、SQS定義の追加が必要 |
| 6 | **Teams Bot登録・接続** | Azure AD アプリ登録、Bot Framework設定。会社のIT管理部門への申請が必要（`docs/phase1-workflow.md` 参照） |

### 優先度: 低（改善・拡張）

| # | 内容 | 詳細 |
|---|---|---|
| 7 | **担当者解決の精度向上** | 現在は完全一致 or 部分一致のみ。あいまい検索（「田中」→「田中太郎」）や、Teamsの送信者名からBacklogユーザーを自動マッピングする仕組みの検討 |
| 8 | **intent_classifierの必須フィールド緩和** | 現在estimated_hours, assigneeが必須。ユーザーが指定しなかった場合にデフォルト値で補完するか、issue_generatorに推測させるかの検討 |
| 9 | **エラーハンドリングの充実** | Claude APIのレート制限、タイムアウト、Backlog APIの4xx/5xxエラー時のリトライ戦略 |
| 10 | **ログ・モニタリング** | CloudWatch Logsへの構造化ログ出力、メトリクス（処理時間、成功/失敗率） |
| 11 | **Slack対応** | フェーズ2（`# TODO(nohara): フェーズ2でSlack対応`） |

---

## 6. Lambda分離設計（受付 / ワーカー分離）

### 背景・課題

現状の `teams_webhook.py` は1つのLambdaで全処理を同期実行している。

```
現在: teams_webhook Lambda（同期・一気通貫）
  HMAC検証 → メッセージ解析 → Claude 1回目 → SSM確認 → Claude 2回目 → Backlog API → レスポンス返却
```

Teams Outgoing Webhook は **5秒以内** にHTTPレスポンスを返さないとタイムアウトする。
Claude API 2回呼び出し + Backlog API で5秒を超える可能性が高い。

### 制約: Outgoing Webhook は HTTP レスポンスでしか返答できない

Teams Outgoing Webhook は Bot Framework と違い **Proactive Message（後から能動的にメッセージ送信）ができない**。
HTTP レスポンスとして返せる1回きりのメッセージが唯一の返答手段。

そのため、処理完了後の結果通知には **Incoming Webhook（別URL）** を使う。
Incoming Webhook は Teams チャネルに追加するだけでURLが発行され、Bot登録やAzure AD申請は不要。

### 変更後のアーキテクチャ

```
[Teams チャネル]
  │
  │ Outgoing Webhook（メンション時に発火）
  ↓
[Lambda A: teams_webhook]（受付専用・軽量）
  → HMAC署名検証
  → メッセージ解析（message_parser）
  → SQS にメッセージをキューイング
  → 即座に「処理中です...しばらくお待ちください。」を返却（5秒以内）
  │
  ↓
[SQS: topal-task-queue]（※LocalStackに作成済み）
  │  ※失敗時 → topal-task-queue-dlq（デッドレターキュー、作成済み）
  ↓
[Lambda B: task_worker]（SQSトリガー・非同期処理）
  → intent_classifier（Claude API 1回目: 意図判定）
  → SSMからプロジェクト設定取得
  → [create] issue_generator（Claude API 2回目: 課題内容生成）→ task_create（Backlog API）
  → [update] task_update（Backlog API）
  → 結果を Teams Incoming Webhook URL に POST
  │
  ↓
[Teams チャネル]
  ← 「タスクを作成しました: NOHARATEST-1 ログイン機能を実装する。」
```

### 変更対象ファイル

| ファイル | 変更内容 |
|---|---|
| `src/handlers/teams_webhook.py` | 受付専用に軽量化。HMAC検証 → SQSキュー投入 → `teams_response.accepted()` 返却のみ |
| `src/handlers/task_worker.py` | **新規作成**。SQSイベントから起動。intent_classifier → issue_generator → task_create/update → Incoming Webhook通知 |
| `src/services/teams_notifier.py` | **新規作成**。Teams Incoming Webhook URLにPOSTして結果を通知するモジュール |
| `src/services/ssm_client.py` | `get_teams_incoming_webhook_url()` を追加 |
| `localstack/init.sh` | SSMに `/topal/teams_incoming_webhook_url` パラメータ追加 |
| `infra/lambda.tf` | Lambda B（task_worker）の定義追加、SQSトリガー設定 |
| `infra/sqs.tf` | **新規作成**。SQSキュー + DLQのTerraform定義 |

### SQSメッセージ形式（Lambda A → SQS → Lambda B）

```json
{
  "message": "画面のログインボタンが押せないバグがあるので課題にしてください",
  "from": {
    "name": "野原 太郎",
    "id": "29:user-aad-id-here"
  },
  "conversation_id": "19:channel-id@thread.tacv2",
  "timestamp": "2026-03-22T10:00:00.000Z"
}
```

### Teams Incoming Webhook への POST

```bash
POST <Incoming Webhook URL>
Content-Type: application/json

{
  "type": "message",
  "text": "タスクを作成しました: NOHARATEST-1 ログイン機能を実装する。"
}
```

### SSMパラメータ追加

```
/topal/teams_incoming_webhook_url   # Teams Incoming Webhook URL (SecureString)
```

### 既存で用意済みのもの

| リソース | 状態 |
|---|---|
| `teams_response.accepted()` | 実装済み（未使用）。「処理中です...しばらくお待ちください。」を返す |
| `topal-task-queue` (SQS) | LocalStack init.sh で作成済み |
| `topal-task-queue-dlq` (SQS DLQ) | LocalStack init.sh で作成済み |

---

## 7. 技術的な判断ログ

| 判断 | 理由 |
|---|---|
| DB削除 → SSMのみ構成 | プロジェクト設定はSSMで十分。Aurora Serverless v2のコスト・複雑さを排除 |
| Claude API 2段階呼び出し | 1回目（intent_classifier）は軽量・高速に意図判定、2回目（issue_generator）は種別選定・テンプレ記入・時間見積もりの重い処理を分離 |
| テンプレートJSON外部ファイル | Backlog種別テンプレート設定とClaude プロンプト注入の両方で使い回すため |
| テンプレート常に上書き | JSONファイルが正（Single Source of Truth）。Backlog側で手動変更しても次回セットアップで上書きされる |
| ステータス上限チェック | Backlog APIの制限（プロジェクト当たり最大12ステータス）に対応。超過時は追加せずエラー返却 |
| 種別は上限チェック不要 | Backlog APIで種別の上限は確認されなかった（20種以上作成可能） |
| DEV/STG/PRD反映ステータス削除 | 不要と判断。5ステータス（AI下書き/遅延-処理中/処理待/レビュー:待/レビュー:済）に絞った |
| QAは「質問」種別 | テスト/品質保証ではなく、特定の誰かに対する質問・確認用途 |
| 予定時間0.5h単位 | Backlogの予定時間入力粒度に合わせた。切り上げ |
| 1日=8.5h | 9:00-17:30の営業時間（休憩なし計算） |

---

## 7. 開発環境情報

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

### 依存パッケージ (`requirements.txt`)

- `anthropic` - Claude API クライアント
- `boto3` - AWS SDK（SSM）
- `requests` - HTTP通信（Backlog API）
- `pytest` - テストフレームワーク

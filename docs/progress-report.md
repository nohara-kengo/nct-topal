# ToPal 開発進捗レポート

最終更新: 2026-03-25

---

## 1. プロジェクト概要

Teams/Slack のメンションメッセージから Backlog の課題を自動起票・更新するサービス。
Claude API で意図判定と課題内容生成を行い、Backlog API で課題を操作する。
日次レポートの自動生成・Backlog Wiki出力にも対応。

### アーキテクチャ（処理フロー）

```
=== チャットからのタスク操作 ===

[Teams / Slack チャネル]
  │
  │ Bot Framework / Slack Event API（メンション時）
  ↓
[Lambda A: teams_webhook / slack_webhook]（受付専用・軽量・5秒）
  → 認証検証（JWT / Slack署名）
  → メッセージ解析（message_parser）
  → SQS にメッセージをキューイング
  → 即座に応答
  │
  ↓
[SQS: topal-task-queue]
  │  ※失敗時 → topal-task-queue-dlq（デッドレターキュー、最大3回リトライ）
  ↓
[Lambda B: task_worker]（SQSトリガー・非同期処理・120秒）
  → intent_classifier（Claude API: 意図判定 + 担当者ID解決）
  → SSMからプロジェクト設定取得
  → [create] issue_generator → task_create（Backlog API）
  → [update] task_update（Backlog API）
  → [report] report_generator → wiki_writer（Backlog Wiki API）
  → チャットに結果通知
  │
  ↓
[Teams / Slack チャネル]
  ← 「✅ タスクを作成しました: NOHARATEST-1 ログイン機能を実装する。」

=== 日次レポート自動生成（スケジュール実行） ===

[EventBridge: 平日8:00 JST]
  │
  ↓
[Lambda C: report_scheduler]（軽量・プロジェクトごとにSQSメッセージ投入）
  → REPORT_PROJECT_KEYS（カンマ区切り）をループ
  → プロジェクトごとに1件ずつSQSへ投入
  │
  ↓
[SQS: topal-task-queue]（既存キューを再利用）
  ↓
[Lambda B: task_worker]（プロジェクトごとに独立実行）
  → scheduled_action=report を検知 → intent分類スキップ
  → 前日WikiからBacklog課題データの前日比を算出
  → report_generator（全体 + 担当者別レポート生成）
  → wiki_writer（Backlog Wikiに作成/更新）
  │
  ↓
[Backlog Wiki]
  ├── 日次レポート/全体/YYYY/MM/DD
  └── 日次レポート/担当者別/YYYY/MM/DD/担当者名
```

---

## 2. 実装済み機能

### 認証・受信
- Bot Framework JWT トークン検証（`bot_auth.py`）— RS256署名、JWKS自動取得・キャッシュ
- メンションタグ除去・HTMLタグ除去（`message_parser.py`）

### Claude API連携（2段階呼び出し + 担当者解決）
- 意図判定（`intent_classifier.py`）— action/project_key/task_id/title/priority/assignee判定、リトライ付き
- **メンバー一覧をプロンプトに渡して担当者IDを直接解決**（日本語/ローマ字/姓のみ等の揺れをClaudeが吸収）
- 課題内容生成（`issue_generator.py`）— 14種別テンプレートから最適なものを選定、リトライ付き

### Backlog連携
- REST APIクライアント（`backlog_client.py`）— 全メソッドにレート制限429リトライ対応
- 担当者あいまい検索（`assignee_resolver.py`）— Claude解決のフォールバック
- タスク作成・更新時に**担当者へ通知**（`notifiedUserId[0]`）
- プロジェクト初期設定（種別13個・テンプレート14種・カスタムステータス5個・カテゴリ）

### 日次レポート
- Backlog課題データを集計し、Backlog Wikiに日次レポートを自動生成（`report_generator.py`）
- 全体レポート + 担当者別レポートの2種類を出力（`wiki_writer.py`）
- 前日Wikiから前日比を算出（ステータス別増減・新規追加・完了・ステータス変更件数）
- 「スケジュール」種別を除外、完了は別枠で集計
- 前営業日計算（土日スキップ）対応
- チャットから手動実行（「レポート出して」）+ EventBridgeスケジュール自動実行（平日8:00 JST）
- スケジュール実行はSQS経由でプロジェクトごとに独立処理（`report_scheduler.py`）

### 通知
- Bot Framework プロアクティブメッセージ（`teams_notifier.py`）— Azure ADトークン取得・キャッシュ、Adaptive Card形式
- Slack通知（`slack_response.py`）— Bot Token認証

### 非同期処理
- SQS キューイング（webhook → SQS → task_worker）
- デッドレターキュー（最大3回リトライ）
- TASK_QUEUE_URL未設定時は同期フォールバック（テスト用）

### インフラ・CI/CD
- Terraform（Lambda 7つ + API Gateway + SQS + EventBridge + IAM + Layer）
- S3バックエンド
- GitHub Actions（ci.yml: テスト + terraform validate、deploy.yml: develop → AWS）

---

## 3. 残件

### IT管理部への依頼（コード実装済み、GUI設定のみ必要）

| # | 内容 | 状態 |
|---|------|------|
| 1 | **Bot Framework 利用許可**（Azure AD アプリ登録 + カスタムアプリ配布） | 確認文面作成済み・未送信 |
| 2 | **Backlog Bot ユーザー作成**（担当者通知のため） | 未申請 |
| 3 | Anthropic API 組織アカウント切り替え | 個人キーで動作中・優先度低 |

### 開発残件

| # | 内容 | 優先度 |
|---|------|--------|
| 1 | IAMユーザー分離（デプロイ専用 or OIDC連携） | 中 |
| 2 | 日次レポートの推移グラフ化（QuickChart API or テキストバーチャート） | 低 |

詳細は [docs/pending-approvals.md](./pending-approvals.md) を参照。

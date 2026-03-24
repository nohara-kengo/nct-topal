# ToPal 開発進捗レポート

最終更新: 2026-03-24

---

## 1. プロジェクト概要

Teams のメンションメッセージから Backlog の課題を自動起票・更新するサービス。
Claude API で意図判定と課題内容生成を行い、Backlog API で課題を操作する。

### アーキテクチャ（処理フロー）

```
[Teams チャネル]
  │
  │ Bot Framework（メンション時にActivity送信）
  ↓
[Lambda A: teams_webhook]（受付専用・軽量）
  → JWT トークン検証（Azure AD 署名）
  → メッセージ解析（message_parser）
  → SQS にメッセージをキューイング（serviceUrl, conversation含む）
  → 即座に「処理中です...しばらくお待ちください。」を返却
  │
  ↓
[SQS: topal-task-queue]
  │  ※失敗時 → topal-task-queue-dlq（デッドレターキュー、最大3回リトライ）
  ↓
[Lambda B: task_worker]（SQSトリガー・非同期処理・120秒）
  → intent_classifier（Claude API: 意図判定 + メンバー一覧から担当者ID解決）
  → SSMからプロジェクト設定取得
  → [create] issue_generator（Claude API: 課題内容生成）
           → task_create（Backlog API + 担当者通知）
  → [update] task_update（Backlog API + 担当者通知）
  → Bot Framework プロアクティブメッセージで結果通知
  │
  ↓
[Teams チャネル]
  ← 「✅ 野原 太郎さんのリクエストでタスクを作成しました: NOHARATEST-1 ログイン機能を実装する。」
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

### 通知
- Bot Framework プロアクティブメッセージ（`teams_notifier.py`）— Azure ADトークン取得・キャッシュ、Adaptive Card形式

### 非同期処理
- SQS キューイング（teams_webhook → SQS → task_worker）
- デッドレターキュー（最大3回リトライ）
- TASK_QUEUE_URL未設定時は同期フォールバック（テスト用）

### インフラ・CI/CD
- Terraform（Lambda 6つ + API Gateway + SQS + IAM + Layer）
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
| 2 | Slack対応（フェーズ2） | 低 |

詳細は [docs/pending-approvals.md](./pending-approvals.md) を参照。

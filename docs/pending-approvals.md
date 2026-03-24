# 残件: 社内申請・承認が必要な項目

## 1. Anthropic API キー

| 項目 | 内容 |
|---|---|
| 何 | Anthropic API のAPIキーとクレジット |
| 費用 | 有料（最低$5〜、従量課金） |
| 用途 | Teamsメッセージの意図判定（新規作成 or 更新、課題キー抽出など） |
| 取得先 | https://console.anthropic.com/ → API Keys |
| 備考 | Claude Pro/Premiumプランとは別サービス・別課金。開発・テスト段階なら月$5〜10程度 |
| ステータス | **SSMに設定済み（個人キー）** → 組織アカウント発行待ち |

## 2. Backlog API キー

| 項目 | 内容 |
|---|---|
| 何 | Backlog APIキー + スペースURL |
| 費用 | 無料（Backlog契約内） |
| 用途 | ToPalからタスクの自動起票・更新 |
| 取得先 | Backlog → 個人設定 → API → 新しいAPIキーを発行 |
| 確認事項 | APIキー発行アカウント（共有 or 個人）、対象プロジェクトキー（例: NOHARATEST）、スペースURL（例: xxxx.backlog.com） |
| SSMパラメータ | `/topal/{PROJECT_KEY}/backlog_api_key` (SecureString), `/topal/{PROJECT_KEY}/backlog_space_url` (String) |
| ステータス | **未確認** — 情報が揃い次第SSMに設定 |

## 3. Teams Outgoing Webhook 登録

| 項目 | 内容 |
|---|---|
| 何 | Teams Outgoing Webhookの作成（チャネル設定） |
| 費用 | 無料 |
| 用途 | @ToPal メンション時にLambda APIへPOSTリクエストを送る |
| 必要な権限 | Teamsチャネルの管理者権限（Webhookの作成権限） |
| 設定内容 | Webhook名: ToPal、コールバックURL: API GatewayのエンドポイントURL（`/webhook/teams`） |
| 取得できるもの | HMACシークレット（Webhook作成時に表示される。HMAC署名検証に使用） |
| SSMパラメータ | `/topal/teams_webhook_secret` (SecureString) |
| 備考 | Azure AD登録は不要（Outgoing Webhook方式のため） |
| ステータス | **IT管理部に問い合わせ文面作成済み・未送信** |

## 4. Teams Incoming Webhook 登録

| 項目 | 内容 |
|---|---|
| 何 | Teams Incoming Webhookの作成（チャネル設定） |
| 費用 | 無料 |
| 用途 | タスク作成・更新完了後の結果通知（非同期処理の結果をチャネルに投稿） |
| 必要な権限 | Teamsチャネルの管理者権限（コネクタの追加権限） |
| 設定内容 | チャネル → コネクタ → Incoming Webhook追加 → URL取得 |
| SSMパラメータ | `/topal/teams_incoming_webhook_url` (String) |
| 備考 | Outgoing Webhookとセットで同じチャネルに設定。Bot登録不要 |
| ステータス | **未申請** — Outgoing Webhook許可と同時に確認 |

## 申請の優先順

1. **Teams Outgoing Webhook + Incoming Webhook の利用許可確認**（IT管理部）→ 許可が下りたらWebhook作成 → secretとURLをSSMに設定
2. **Backlog API キー・スペースURL の確認** → SSMパラメータ設定 → 結合テスト可能に
3. **Anthropic API 組織アカウントでのキー発行** → 個人キーから切り替え

## SSMパラメータ設定状況

| パラメータ | 状態 | 依存 |
|-----------|------|------|
| `/topal/anthropic_api_key` | ✅ 設定済み（個人キー） | — |
| `/topal/claude_model` | ✅ 設定済み | — |
| `/topal/teams_webhook_secret` | ❌ 未設定 | Outgoing Webhook作成後 |
| `/topal/teams_incoming_webhook_url` | ❌ 未設定 | Incoming Webhook作成後 |
| `/topal/{PROJECT_KEY}/backlog_api_key` | ❌ 未設定 | Backlog情報確認後 |
| `/topal/{PROJECT_KEY}/backlog_space_url` | ❌ 未設定 | Backlog情報確認後 |

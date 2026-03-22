# 残件: 社内申請・承認が必要な項目

## 1. Anthropic API キー

| 項目 | 内容 |
|---|---|
| 何 | Anthropic API のAPIキーとクレジット |
| 費用 | 有料（最低$5〜、従量課金） |
| 用途 | Teamsメッセージの意図判定（新規作成 or 更新、課題キー抽出など） |
| 取得先 | https://console.anthropic.com/ → API Keys |
| 備考 | Claude Pro/Premiumプランとは別サービス・別課金。開発・テスト段階なら月$5〜10程度 |
| ステータス | 未申請 |

## 2. Backlog API キー

| 項目 | 内容 |
|---|---|
| 何 | Backlog APIキー |
| 費用 | 無料（Backlog契約内） |
| 用途 | ToPalからタスクの自動起票・更新 |
| 取得先 | Backlog → 個人設定 → API → 新しいAPIキーを発行 |
| 確認事項 | APIキー発行アカウント（共有 or 個人）、対象プロジェクトキー（例: PROJ）、スペースURL（例: xxxx.backlog.jp） |
| ステータス | 未申請 |

## 3. Teams Outgoing Webhook 登録

| 項目 | 内容 |
|---|---|
| 何 | Teams Outgoing Webhookの作成（チャネル設定） |
| 費用 | 無料 |
| 用途 | @ToPal メンション時にLambda APIへPOSTリクエストを送る |
| 必要な権限 | Teamsチャネルの管理者権限（Webhookの作成権限） |
| 設定内容 | Webhook名: ToPal、コールバックURL: API GatewayのエンドポイントURL（`/webhook/teams`） |
| 取得できるもの | HMACシークレット（Webhook作成時に表示される。HMAC署名検証に使用） |
| 備考 | Azure AD登録は不要（Outgoing Webhook方式のため） |
| ステータス | 未申請 |

## 申請の優先順

1. **Anthropic API キー** — これがないとClaude APIの実呼び出しテストができない
2. **Backlog API キー** — タスク起票の実装に必要
3. **Teams Outgoing Webhook** — 結合テストの最終段階で必要（API Gatewayデプロイ後）

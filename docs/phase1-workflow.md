# フェーズ1 ワークフロー

## 事前準備・確認事項

### Teams（会社資産のため要確認）

| 項目 | 内容 | 確認先 |
|---|---|---|
| カスタムアプリの許可 | TeamsにBotアプリをインストールするにはMicrosoft 365管理者の許可が必要 | IT管理部門 / M365管理者 |
| Azure ADアプリ登録 | Teams Botを動かすにはAzure ADにアプリ登録が必要（Bot Framework） | IT管理部門 |
| サイドローディング許可 | 開発中のBotをTeamsにインストールするにはサイドローディングが有効である必要がある | M365管理センター |
| 送受信データの取り扱い | スレッド内容を外部API（Claude API）に送信する点のセキュリティ確認 | 情報セキュリティ部門 |
| 対象チャネルの範囲 | 全チャネルか、特定チャネルのみに限定するか | PO / チームリーダー |

> **注意**: Teams関連は会社のポリシーによって制約が大きいため、開発着手前に上記を確認すること。許可が下りない場合はOutgoing Webhookでの代替も検討する。

### AWS

| 項目 | 内容 |
|---|---|
| AWSアカウント | Lambda, API Gatewayが利用可能なアカウントを用意 |
| API Gateway | TeamsからのWebhookを受けるエンドポイント |
| Secrets Manager | Claude API Key, Backlog API Keyの管理 |

### 外部サービス

| 項目 | 内容 |
|---|---|
| Claude API Key | Anthropic APIキーの取得 |
| Backlog API Key | 対象プロジェクトへの起票権限があるAPIキーの取得 |
| Backlogカスタムステータス | 「AI下書き」「AI起票済み」ステータスの追加 |

## 開発ステップ

```mermaid
flowchart TD
    S1[1. 事前確認・承認取得] --> S2[2. AWS基盤構築]
    S2 --> S3[3. Teams Bot登録・接続]
    S3 --> S4[4. メッセージ受信Lambda実装]
    S4 --> S5[5. Claude API連携実装]
    S5 --> S6[6. Backlog起票実装]
    S6 --> S7[7. スレッド返信実装]
    S7 --> S8[8. 結合テスト・動作検証]
```

| ステップ | 内容 | ブランチ |
|---|---|---|
| 1. 事前確認 | Teams管理者への申請、APIキー取得、Backlogステータス追加 | - |
| 2. AWS基盤構築 | Lambda + API Gateway + Secrets Manager のセットアップ | `feature/○○/infra` |
| 3. Teams Bot登録 | Azure AD アプリ登録、Bot Framework設定、Webhook接続 | `feature/○○/teams-webhook` |
| 4. メッセージ受信 | TeamsからのWebhookを受け取りスレッド内容を取得するLambda | `feature/○○/teams-webhook` |
| 5. Claude API連携 | スレッド内容をClaude APIに送りサマリー・優先度・期限を取得 | `feature/○○/task-create` |
| 6. Backlog起票 | Claude APIの結果をもとに「AI下書き」ステータスで課題作成 | `feature/○○/task-create` |
| 7. スレッド返信 | 起票完了後、元スレッドにBacklog課題URLを返信 | `feature/○○/teams-webhook` |
| 8. 結合テスト | E2Eでの動作検証（テスト用チャネルで実施） | `develop` |

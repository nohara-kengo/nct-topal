# 残件: 社内申請・承認が必要な項目

## 1. Teams Bot Framework（Azure AD アプリ登録）

| 項目 | 内容 |
|---|---|
| 何 | Azure AD にアプリ登録 + Teams Bot として配布 |
| 費用 | 無料（Azure Bot Channels は無料枠） |
| 用途 | Teams メッセージの受信（JWT認証）と結果通知（プロアクティブメッセージ） |
| 必要な権限 | Azure AD アプリ登録権限、Teams 管理センターでのカスタムアプリ配布許可 |
| 現状 | Teams アプリストアに「組織専用に構築」タブが表示されない → カスタムアプリのアップロードが制限されている |
| コード | **実装済み**（JWT検証・プロアクティブメッセージ対応済み） |
| SSMパラメータ | `/topal/microsoft_app_id` (String), `/topal/microsoft_app_password` (SecureString) |
| ステータス | **IT管理部に確認文面作成済み・未送信** |

### IT管理部への依頼事項
1. Azure AD にアプリを登録（Bot Channels Registration）
2. Teams 管理センターで Bot アプリの組織内配布を許可（「組織専用に構築」タブの有効化）
3. 必要に応じて API アクセス許可の承認（admin consent）

### 許可が下りたら行うこと（GUI操作のみ、コード変更不要）
1. Azure Portal → Azure AD → アプリの登録 → 新規登録 → App ID とシークレットを取得
2. Azure Portal → Azure Bot → 作成 → メッセージングエンドポイントに API Gateway URL（`/webhook/teams`）を設定
3. アプリパッケージ（manifest.json + アイコン）を作成して Teams にアップロード
4. SSM パラメータを設定:
   ```bash
   aws ssm put-parameter --name "/topal/microsoft_app_id" --value "<App ID>" --type String --region ap-northeast-1
   aws ssm put-parameter --name "/topal/microsoft_app_password" --value "<シークレット>" --type SecureString --region ap-northeast-1
   ```
5. デプロイ → Teams からの疎通確認

## 2. Slack アプリのインストール許可

| 項目 | 内容 |
|---|---|
| 何 | Slack ワークスペースへのカスタムアプリインストール許可 |
| 費用 | 無料 |
| 用途 | Slack メンションからのタスク起票・更新・日次レポート生成 |
| 必要な権限 | ワークスペース管理者によるアプリインストール承認 |
| 現状 | コード実装済み（署名検証・Bot Token通知対応済み） |
| SSMパラメータ | `/topal/slack_signing_secret` (SecureString), `/topal/slack_bot_token` (SecureString) |
| ステータス | **未申請** |

### IT管理部への依頼事項
1. Slack ワークスペースへのカスタムアプリインストールを許可
2. Bot Token Scopes の承認: `chat:write`, `app_mentions:read`
3. Event Subscriptions の有効化（Request URL: `https://<API Gateway URL>/webhook/slack`）

### 許可が下りたら行うこと（GUI操作のみ、コード変更不要）
1. api.slack.com → Create New App → From scratch → ワークスペースを選択
2. OAuth & Permissions → Bot Token Scopes に `chat:write`, `app_mentions:read` を追加
3. Event Subscriptions → Enable Events → Request URL に `https://<API Gateway URL>/webhook/slack` を設定
4. Event Subscriptions → Subscribe to bot events → `app_mention` を追加
5. Install App → ワークスペースにインストール → Bot User OAuth Token を取得
6. Basic Information → Signing Secret を取得
7. SSM パラメータを設定:
   ```bash
   aws ssm put-parameter --name "/topal/slack_signing_secret" --value "<Signing Secret>" --type SecureString --region ap-northeast-1
   aws ssm put-parameter --name "/topal/slack_bot_token" --value "<Bot User OAuth Token>" --type SecureString --region ap-northeast-1
   ```
8. 対象チャネルにアプリを追加 → メンションで疎通確認

## 3. Backlog Bot ユーザー作成

| 項目 | 内容 |
|---|---|
| 何 | Backlog に ToPal Bot 用の共有ユーザーを追加 |
| 費用 | 無料（Backlog契約内） |
| 用途 | Bot 経由でタスク作成・更新時に、担当者へ通知を届けるため（自分→自分の操作は通知されないため） |
| 現状 | 個人アカウントの API キーで運用中 → 担当者=APIキー所有者だと通知が届かない |
| ステータス | **未申請** |

### 必要な作業
1. Backlog 管理者に「ToPal Bot」ユーザーの追加を依頼
2. Bot ユーザーを対象プロジェクト（NOHARATEST 等）に追加
3. Bot ユーザーの API キーを発行 → SSM パラメータを差し替え

## 4. Anthropic API 組織アカウント

| 項目 | 内容 |
|---|---|
| 何 | Anthropic API のAPIキーとクレジット |
| 費用 | 有料（従量課金、開発・テスト段階なら月$5〜10程度） |
| 用途 | Teamsメッセージの意図判定・課題内容生成 |
| ステータス | **SSMに設定済み（個人キー）** → 組織アカウント発行待ち |

## 5. 管理画面 + DB（将来構想）

| 項目 | 内容 |
|---|---|
| 何 | ToPalの機能・プロジェクトを管理するWebダッシュボード + 設定DB |
| 技術 | React + Aurora PostgreSQL Serverless v2 |
| 追加コスト | VPC + NAT Gateway + Aurora + RDS Proxy で ~$110/月 |
| ステータス | **予算確保待ち（現状はSSM手動設定で運用）** |

## SSMパラメータ設定状況

| パラメータ | 状態 | 依存 |
|-----------|------|------|
| `/topal/anthropic_api_key` | ✅ 設定済み（個人キー） | — |
| `/topal/claude_model` | ✅ 設定済み | — |
| `/topal/microsoft_app_id` | ❌ 未設定 | Bot Framework 許可後 |
| `/topal/microsoft_app_password` | ❌ 未設定 | Bot Framework 許可後 |
| `/topal/slack_signing_secret` | ❌ 未設定 | Slack アプリインストール許可後 |
| `/topal/slack_bot_token` | ❌ 未設定 | Slack アプリインストール許可後 |
| `/topal/{PROJECT_KEY}/backlog_api_key` | ✅ 設定済み（個人キー） | Bot ユーザー作成後に差し替え |
| `/topal/{PROJECT_KEY}/backlog_space_url` | ✅ 設定済み | — |

# AWSインフラ構成図

```mermaid
graph TB
    subgraph Microsoft["Microsoft"]
        Teams["Microsoft Teams"]
        BotFW["Azure Bot Framework<br/>JWT認証 / プロアクティブメッセージ"]
    end

    subgraph Anthropic["Anthropic"]
        Claude["Claude API"]
    end

    subgraph Nulab["Nulab"]
        Backlog["Backlog API"]
    end

    subgraph AWS["AWS（ap-northeast-1）"]
        subgraph APIGW["API Gateway HTTP API<br/>topal-dev-api"]
            R2["POST /tasks"]
            R3["PUT /tasks/{taskId}"]
            R4["POST /webhook/teams"]
        end

        subgraph Lambda["Lambda Functions"]
            L2["task_create"]
            L3["task_update"]
            L4["teams_webhook"]
            L5["task_worker"]
        end

        Layer["Lambda Layer<br/>（dependencies）"]

        subgraph SQS["Amazon SQS"]
            Q1["topal-task-queue<br/>可視性300s / 保持1日"]
            DLQ["topal-task-queue-dlq<br/>保持14日"]
        end

        SSM["SSM Parameter Store<br/>/topal/*"]

        S3["S3<br/>terraform state"]
    end

    Teams -->|Activity送信| BotFW
    BotFW -->|POST /webhook/teams| APIGW

    R2 --> L2
    R3 --> L3
    R4 --> L4

    L4 -->|SendMessage| Q1
    Q1 -->|EventSourceMapping| L5
    Q1 -->|maxReceiveCount=3| DLQ

    L2 --> Claude
    L2 --> Backlog
    L3 --> Backlog
    L5 --> Claude
    L5 --> Backlog
    L5 -->|プロアクティブメッセージ| BotFW
    BotFW -->|結果通知| Teams

    L2 -.-> Layer
    L3 -.-> Layer
    L4 -.-> Layer
    L5 -.-> Layer

    L2 -.-> SSM
    L3 -.-> SSM
    L4 -.-> SSM
    L5 -.-> SSM
```

## リソース一覧

| サービス | リソース名 | 用途 |
|---------|-----------|------|
| API Gateway | topal-dev-api | HTTPルーティング（4エンドポイント） |
| Lambda | topal-dev-task-create | タスク新規作成 |
| Lambda | topal-dev-task-update | タスク更新 |
| Lambda | topal-dev-teams-webhook | Teams受付（JWT検証→SQSキュー→即応答） |
| Lambda | topal-dev-task-worker | 非同期処理（Claude API→Backlog→通知） |
| Lambda Layer | topal-dev-deps | Python依存パッケージ共有 |
| SQS | topal-task-queue | 受付→ワーカー間の非同期キュー |
| SQS | topal-task-queue-dlq | デッドレターキュー（3回失敗で移動） |
| SSM | /topal/* | APIキー・プロジェクト設定 |
| S3 | nct-topal-tfstate | Terraform state管理 |

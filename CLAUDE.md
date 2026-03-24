# CLAUDE.md
# チーム全員のClaude Codeが参照する共有設定ファイル（gitにコミットする）

## プロジェクト概要
ToPal - Teams/Slackのスレッドからタスクを自動起票するサービス（AWS Lambda + Claude API + Backlog）

## 技術スタック
- Python 3.12
- Terraform (Lambda + API Gateway)
- Claude API (anthropic)

## ディレクトリ構成
- `src/handlers/` - Lambda関数ハンドラー
- `src/services/` - ビジネスロジック・外部サービス連携
- `tests/` - pytest によるテスト
- `infra/` - Terraform設定
- `docs/` - ドキュメント

## 開発環境
- Docker Compose で開発（`docker compose up -d` でアプリ＋LocalStack起動）
- テスト実行: `docker exec topal-dev python -m pytest tests/ -v`

## ブランチ戦略
- `main` → `develop` → `feature/<担当者名>/<機能名>`
- feature は develop にPR、develop から main にマージ

## コーディング規約

### 基本
- 日本語でコミュニケーション
- Lambda ハンドラーは `src/handlers/` に配置
- テストは `tests/` に `test_*.py` で配置

### docstring方針
- Google スタイルで記述する
- 言語は日本語
- **書く対象**:
  - モジュール（ファイル）の先頭 — そのファイルの責務を1行で
  - 公開関数・クラス — 何をするか・引数・戻り値
  - Lambdaハンドラー — 対応するAPIパス・メソッドを明記
- **書かない対象**:
  - プライベート関数（`_` prefix）で処理が自明なもの
  - テストコード（テスト名で意図が伝わるようにする）
  - `__init__.py`

### docstring例

```python
"""Teamsメッセージを受信してタスク起票を行うハンドラー。"""


def handler(event, context):
    """ヘルスチェックエンドポイント。

    API: GET /health

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        statusCode 200 と {"status": "ok"} を返す
    """
```

### インラインコメント方針
- 「なぜ（Why）」を書く。「何を（What）」はコードで表現する
- 一時的な回避策やハック的な処理には必ず理由を書く
- TODOコメントには担当者と対応時期を書く: `# TODO(nohara): フェーズ2でSlack対応`

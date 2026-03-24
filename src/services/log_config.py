"""CloudWatch向けJSON構造化ログの設定モジュール。"""

import json
import logging
import os
import sys


class JsonFormatter(logging.Formatter):
    """CloudWatch Logs向けのJSON構造化フォーマッター。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Lambda環境のリクエストIDがあれば付与
        if hasattr(record, "aws_request_id"):
            log_entry["request_id"] = record.aws_request_id

        # 追加コンテキスト（extra引数で渡されたもの）
        for key in ("project_key", "action", "sender_name", "issue_key", "task_id"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        # 例外情報
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: str | None = None) -> None:
    """ルートロガーにJSON構造化ログを設定する。

    Lambda環境（AWS_LAMBDA_FUNCTION_NAME設定時）のみJSON形式を使用し、
    ローカル開発では通常のテキスト形式を維持する。

    Args:
        level: ログレベル（デフォルト: LOG_LEVEL環境変数 or INFO）
    """
    log_level = level or os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    root.setLevel(log_level)

    # Lambda環境かどうかで分岐
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        # Lambda環境: JSON構造化ログ
        # Lambda Runtimeが追加するデフォルトハンドラーを除去
        root.handlers.clear()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)

"""Bot Frameworkへのレスポンスを生成するモジュール。"""

import json


def success(message: str) -> dict:
    """成功レスポンスを生成する。

    Args:
        message: Teamsに表示するメッセージ

    Returns:
        API Gateway形式のレスポンスdict
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"type": "message", "text": message}, ensure_ascii=False),
    }


def accepted() -> dict:
    """処理受付レスポンスを生成する（5秒タイムアウト対策）。

    Returns:
        API Gateway形式のレスポンスdict
    """
    return success("処理中です...しばらくお待ちください。")


def error(message: str = "処理中にエラーが発生しました。", status_code: int = 200) -> dict:
    """エラーレスポンスを生成する。

    Bot Frameworkではエラー時もメッセージとして返しユーザーに通知する。

    Args:
        message: エラーメッセージ
        status_code: HTTPステータスコード（デフォルト200）

    Returns:
        API Gateway形式のレスポンスdict
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"type": "message", "text": message}, ensure_ascii=False),
    }

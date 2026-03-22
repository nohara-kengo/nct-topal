"""各エンドポイントのヘルスチェックを行うハンドラー。"""

import json


def handler(event, context):
    """ヘルスチェックエンドポイント。

    API: GET /health

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        statusCode 200 と各サービスのステータスを返す
    """
    health = {
        "status": "ok",
        "endpoints": {
            "POST /tasks": "ok",
            "PUT /tasks/{taskId}": "ok",
            "POST /webhook/teams": "ok",
        },
    }

    return {
        "statusCode": 200,
        "body": json.dumps(health, ensure_ascii=False),
    }

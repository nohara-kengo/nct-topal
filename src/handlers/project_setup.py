"""プロジェクトの初期設定（種別・カテゴリ・ステータス）を行うハンドラー。"""

import json
import logging

from src.services import backlog_setup
from src.services.backlog_setup import StatusLimitExceeded

logger = logging.getLogger(__name__)


def handler(event, context):
    """プロジェクト初期設定エンドポイント。

    API: POST /projects/{projectKey}/setup

    種別・カテゴリ・ステータスを確認し、未設定のものを作成する。

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        statusCode 200 と設定結果を返す
    """
    project_key = event.get("pathParameters", {}).get("projectKey", "")
    if not project_key:
        body = json.loads(event.get("body") or "{}")
        project_key = body.get("project_key", "")

    if not project_key:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "project_key は必須です"}, ensure_ascii=False),
        }

    logger.info("プロジェクト '%s' の初期設定を開始", project_key)

    try:
        issue_types = backlog_setup.ensure_issue_types(project_key)
        templates = backlog_setup.ensure_issue_type_templates(project_key)
        statuses = backlog_setup.ensure_statuses(project_key)
        category_id = backlog_setup._ensure_category(project_key)
    except StatusLimitExceeded as e:
        logger.warning("ステータス上限エラー: %s", e)
        return {
            "statusCode": 409,
            "body": json.dumps({"error": str(e)}, ensure_ascii=False),
        }
    except Exception:
        logger.exception("プロジェクト初期設定に失敗: %s", project_key)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "プロジェクト初期設定に失敗しました"}, ensure_ascii=False),
        }

    result = {
        "project_key": project_key,
        "issue_types": issue_types,
        "templates": templates,
        "statuses": statuses,
        "category_ai_generated_id": category_id,
    }

    logger.info("プロジェクト '%s' の初期設定が完了", project_key)

    return {
        "statusCode": 200,
        "body": json.dumps(result, ensure_ascii=False),
    }

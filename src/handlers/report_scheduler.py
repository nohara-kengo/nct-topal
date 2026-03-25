"""EventBridgeスケジュールからSQS経由で日次レポート生成を起動するハンドラー。"""

import json
import logging
import os

import boto3

from src.services.log_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_SQS_QUEUE_URL = os.environ.get("TASK_QUEUE_URL")


def _get_sqs_client():
    kwargs = {"region_name": os.environ.get("AWS_REGION", "ap-northeast-1")}
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("sqs", **kwargs)


def handler(event, context):
    """日次レポートのスケジュール実行エンドポイント。

    API: EventBridge Schedule → Lambda

    環境変数 REPORT_PROJECT_KEYS（カンマ区切り）で指定されたプロジェクトごとに
    SQSメッセージを投入し、task_workerで個別にレポートを生成させる。

    Args:
        event: EventBridgeイベント
        context: Lambda コンテキスト

    Returns:
        処理結果のサマリー
    """
    project_keys_str = os.environ.get("REPORT_PROJECT_KEYS", "")
    if not project_keys_str:
        logger.warning("REPORT_PROJECT_KEYS が未設定のためスキップ")
        return {"status": "skipped", "reason": "no_project_keys"}

    if not _SQS_QUEUE_URL:
        logger.error("TASK_QUEUE_URL が未設定")
        return {"status": "error", "reason": "no_queue_url"}

    project_keys = [k.strip() for k in project_keys_str.split(",") if k.strip()]
    sqs = _get_sqs_client()

    enqueued = []
    for project_key in project_keys:
        msg = {
            "scheduled_action": "report",
            "project_key": project_key,
        }
        try:
            sqs.send_message(
                QueueUrl=_SQS_QUEUE_URL,
                MessageBody=json.dumps(msg, ensure_ascii=False),
            )
            logger.info("レポートSQSメッセージ投入: %s", project_key)
            enqueued.append(project_key)
        except Exception:
            logger.exception("SQS送信失敗: %s", project_key)

    return {"status": "completed", "enqueued": enqueued}

import json
from unittest.mock import patch, MagicMock, call

from src.handlers import report_scheduler


QUEUE_URL = "https://sqs.ap-northeast-1.amazonaws.com/123/topal-task-queue"


@patch.dict("os.environ", {"REPORT_PROJECT_KEYS": "PROJ1,PROJ2", "TASK_QUEUE_URL": QUEUE_URL})
@patch("src.handlers.report_scheduler._get_sqs_client")
def test_scheduler_enqueues_per_project(mock_sqs_factory):
    # TASK_QUEUE_URLをモジュール変数に反映
    report_scheduler._SQS_QUEUE_URL = QUEUE_URL

    mock_sqs = MagicMock()
    mock_sqs_factory.return_value = mock_sqs

    result = report_scheduler.handler({}, None)

    assert result["status"] == "completed"
    assert result["enqueued"] == ["PROJ1", "PROJ2"]
    assert mock_sqs.send_message.call_count == 2

    # 各メッセージの内容を検証
    calls = mock_sqs.send_message.call_args_list
    body0 = json.loads(calls[0][1]["MessageBody"])
    body1 = json.loads(calls[1][1]["MessageBody"])
    assert body0 == {"scheduled_action": "report", "project_key": "PROJ1"}
    assert body1 == {"scheduled_action": "report", "project_key": "PROJ2"}

    report_scheduler._SQS_QUEUE_URL = None


@patch.dict("os.environ", {"REPORT_PROJECT_KEYS": ""})
def test_scheduler_no_project_keys():
    result = report_scheduler.handler({}, None)
    assert result["status"] == "skipped"


@patch.dict("os.environ", {"REPORT_PROJECT_KEYS": "PROJ1"})
def test_scheduler_no_queue_url():
    report_scheduler._SQS_QUEUE_URL = None
    result = report_scheduler.handler({}, None)
    assert result["status"] == "error"
    assert result["reason"] == "no_queue_url"


@patch.dict("os.environ", {"REPORT_PROJECT_KEYS": "GOOD,BAD", "TASK_QUEUE_URL": QUEUE_URL})
@patch("src.handlers.report_scheduler._get_sqs_client")
def test_scheduler_partial_sqs_failure(mock_sqs_factory):
    """1プロジェクトのSQS送信が失敗しても他は投入される。"""
    report_scheduler._SQS_QUEUE_URL = QUEUE_URL

    mock_sqs = MagicMock()
    mock_sqs_factory.return_value = mock_sqs

    def side_effect(**kwargs):
        body = json.loads(kwargs["MessageBody"])
        if body["project_key"] == "BAD":
            raise Exception("SQS error")

    mock_sqs.send_message.side_effect = side_effect

    result = report_scheduler.handler({}, None)

    assert result["enqueued"] == ["GOOD"]
    assert mock_sqs.send_message.call_count == 2

    report_scheduler._SQS_QUEUE_URL = None


# --- task_worker側のスケジュールレポート処理テスト ---

from src.handlers import task_worker


@patch("src.handlers.task_worker.wiki_writer")
@patch("src.handlers.task_worker.report_generator")
@patch("src.handlers.task_worker.ssm_client")
def test_worker_scheduled_report(mock_ssm, mock_rg, mock_ww):
    mock_rg.get_prev_business_date_path.return_value = "2026/03/24"
    mock_ww.fetch_prev_wikis.return_value = {}
    mock_rg.generate_daily_report.return_value = {
        "summary": {"total": 5},
        "pages": [{"name": "p1", "content": "c1"}, {"name": "p2", "content": "c2"}],
    }

    event = {
        "Records": [{
            "messageId": "test-1",
            "body": json.dumps({"scheduled_action": "report", "project_key": "NOHARATEST"}),
        }]
    }

    result = task_worker.handler(event, None)

    assert result["processed"] == 1
    mock_rg.generate_daily_report.assert_called_once()
    mock_ww.write_daily_report.assert_called_once()

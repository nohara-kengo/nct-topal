import json
from unittest.mock import patch, MagicMock

from src.handlers.task_worker import handler


MOCK_SERVICE_URL = "https://smba.trafficmanager.net/jp"
MOCK_CONVERSATION = {"id": "19:test@thread.tacv2"}

MOCK_INTENT_CREATE = {
    "action": "create",
    "project_key": "NOHARATEST",
    "task_id": None,
    "title": "新しいタスク",
    "priority": "中",
    "estimated_hours": 4.0,
    "assignee": "野原",
    "assignee_id": None,
}

MOCK_INTENT_UPDATE = {
    "action": "update",
    "project_key": "NOHARATEST",
    "task_id": "NOHARATEST-3",
    "title": "優先度変更",
    "priority": "高",
    "estimated_hours": 1.0,
    "assignee": "野原",
    "assignee_id": None,
}

MOCK_GENERATED = {
    "issue_type": "タスク",
    "title": "新しいタスクを実装する。",
    "description": "# 目的\nテスト",
    "estimated_hours": 4.0,
}


def _make_sqs_event(message: str, sender_name: str = "野原 太郎") -> dict:
    return {
        "Records": [{
            "messageId": "test-msg-001",
            "body": json.dumps({
                "message": message,
                "sender_name": sender_name,
                "service_url": MOCK_SERVICE_URL,
                "conversation": MOCK_CONVERSATION,
            }, ensure_ascii=False),
        }],
    }


@patch("src.handlers.task_worker.ssm_client.get_backlog_space_url", return_value="https://comthink06.backlog.com")
@patch("src.handlers.task_worker.teams_notifier.notify")
@patch("src.handlers.task_worker.task_create.handler")
@patch("src.handlers.task_worker.issue_generator.generate", return_value=MOCK_GENERATED)
@patch("src.handlers.task_worker.ssm_client.get_backlog_api_key", return_value="dummy")
@patch("src.handlers.task_worker.backlog_client.get_project_users", return_value=[])
@patch("src.handlers.task_worker.intent_classifier.classify", return_value=MOCK_INTENT_CREATE)
def test_worker_create(mock_classify, mock_users, mock_ssm, mock_generate, mock_create, mock_notify, mock_space_url):
    mock_create.return_value = {
        "statusCode": 201,
        "body": json.dumps({"id": "NOHARATEST-99", "title": "新しいタスクを実装する。", "status": "AI下書き"}),
    }

    event = _make_sqs_event("[NOHARATEST] 新しいタスクを作って")
    result = handler(event, None)

    assert result["processed"] == 1
    assert mock_notify.call_count == 2
    # 1回目: 処理中メッセージ
    assert "処理中" in mock_notify.call_args_list[0].args[0]
    # 2回目: 完了メッセージ
    result_msg = mock_notify.call_args_list[1].args[0]
    assert "作成しました" in result_msg
    assert "NOHARATEST-99" in result_msg
    assert "処理を完了しました" in result_msg
    assert mock_notify.call_args_list[1].args[1] == MOCK_SERVICE_URL
    assert mock_notify.call_args_list[1].args[2] == MOCK_CONVERSATION


@patch("src.handlers.task_worker.ssm_client.get_backlog_space_url", return_value="https://comthink06.backlog.com")
@patch("src.handlers.task_worker.teams_notifier.notify")
@patch("src.handlers.task_worker.task_update.handler")
@patch("src.handlers.task_worker.ssm_client.get_backlog_api_key", return_value="dummy")
@patch("src.handlers.task_worker.backlog_client.get_project_users", return_value=[])
@patch("src.handlers.task_worker.intent_classifier.classify", return_value=MOCK_INTENT_UPDATE)
def test_worker_update(mock_classify, mock_users, mock_ssm, mock_update, mock_notify, mock_space_url):
    mock_update.return_value = {
        "statusCode": 200,
        "body": json.dumps({"id": "NOHARATEST-3", "title": "優先度変更", "status": "処理中"}),
    }

    event = _make_sqs_event("NOHARATEST-3の優先度を高に変更")
    result = handler(event, None)

    assert result["processed"] == 1
    assert mock_notify.call_count == 2
    assert "処理中" in mock_notify.call_args_list[0].args[0]
    result_msg = mock_notify.call_args_list[1].args[0]
    assert "更新しました" in result_msg
    assert "NOHARATEST-3" in result_msg
    assert "comthink06.backlog.com" in result_msg
    assert "処理を完了しました" in result_msg


@patch("src.handlers.task_worker.ssm_client.get_channel_project_key", return_value="NOHARATEST")
@patch("src.handlers.task_worker.ssm_client.get_backlog_space_url", return_value="https://comthink06.backlog.com")
@patch("src.handlers.task_worker.teams_notifier.notify")
@patch("src.handlers.task_worker.task_create.handler")
@patch("src.handlers.task_worker.issue_generator.generate", return_value=MOCK_GENERATED)
@patch("src.handlers.task_worker.ssm_client.get_backlog_api_key", return_value="dummy")
@patch("src.handlers.task_worker.backlog_client.get_project_users", return_value=[])
@patch("src.handlers.task_worker.intent_classifier.classify")
def test_worker_channel_mapping_fallback(mock_classify, mock_users, mock_ssm, mock_generate, mock_create, mock_notify, mock_space_url, mock_channel_map):
    """チャネルマッピングからプロジェクトキーを解決できるケース。"""
    mock_classify.return_value = {
        "action": "create",
        "project_key": None,
        "task_id": None,
        "title": "新しいタスク",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "野原",
        "assignee_id": None,
    }
    mock_create.return_value = {
        "statusCode": 201,
        "body": json.dumps({"id": "NOHARATEST-50", "title": "新しいタスク", "status": "AI下書き"}),
    }

    event = _make_sqs_event("新しいタスクを作って")
    result = handler(event, None)

    assert result["processed"] == 1
    mock_channel_map.assert_called_once_with("19:test@thread.tacv2")
    assert mock_create.called


@patch("src.handlers.task_worker.ssm_client.get_channel_project_key", return_value="MAPPED")
@patch("src.handlers.task_worker.ssm_client.get_backlog_space_url", return_value="https://comthink06.backlog.com")
@patch("src.handlers.task_worker.teams_notifier.notify")
@patch("src.handlers.task_worker.task_create.handler")
@patch("src.handlers.task_worker.issue_generator.generate", return_value=MOCK_GENERATED)
@patch("src.handlers.task_worker.ssm_client.get_backlog_api_key", return_value="dummy")
@patch("src.handlers.task_worker.backlog_client.get_project_users", return_value=[])
@patch("src.handlers.task_worker.intent_classifier.classify", return_value=MOCK_INTENT_CREATE)
def test_worker_explicit_key_overrides_channel_mapping(mock_classify, mock_users, mock_ssm, mock_generate, mock_create, mock_notify, mock_space_url, mock_channel_map):
    """メッセージ内の[KEY]がチャネルマッピングを上書きするケース。"""
    mock_create.return_value = {
        "statusCode": 201,
        "body": json.dumps({"id": "NOHARATEST-99", "title": "新しいタスク", "status": "AI下書き"}),
    }

    event = _make_sqs_event("[NOHARATEST] 新しいタスクを作って")
    result = handler(event, None)

    assert result["processed"] == 1
    # Claude判定でproject_keyが返っているのでチャネルマッピングは呼ばれない
    mock_channel_map.assert_not_called()


@patch("src.handlers.task_worker.teams_notifier.notify")
@patch("src.handlers.task_worker.intent_classifier.classify")
def test_worker_no_project_key(mock_classify, mock_notify):
    mock_classify.return_value = {
        "action": "create",
        "project_key": None,
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": None,
        "assignee": None,
        "assignee_id": None,
    }

    event = _make_sqs_event("タスクを作って")
    result = handler(event, None)

    assert result["processed"] == 1
    assert mock_notify.call_count == 2
    assert "処理中" in mock_notify.call_args_list[0].args[0]
    assert "プロジェクトキー" in mock_notify.call_args_list[1].args[0]

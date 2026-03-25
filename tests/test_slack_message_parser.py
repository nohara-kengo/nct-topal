from src.services.slack_message_parser import strip_mentions, extract_text


def test_strip_single_mention():
    assert strip_mentions("<@U12345> タスク作成") == "タスク作成"


def test_strip_multiple_mentions():
    assert strip_mentions("<@U12345> <@U67890> タスク作成") == "タスク作成"


def test_strip_mention_only():
    assert strip_mentions("<@U12345>") == ""


def test_no_mention():
    assert strip_mentions("タスク作成") == "タスク作成"


def test_empty_string():
    assert strip_mentions("") == ""


def test_extract_text_from_payload():
    payload = {
        "event": {
            "type": "app_mention",
            "text": "<@UBOTID> [NOHARATEST] バグ修正",
        }
    }
    assert extract_text(payload) == "[NOHARATEST] バグ修正"


def test_extract_text_empty_payload():
    assert extract_text({}) == ""
    assert extract_text({"event": {}}) == ""

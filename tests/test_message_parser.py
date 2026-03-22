from src.services.message_parser import strip_mentions, extract_text


def test_strip_single_mention():
    text = "<at>ToPal</at> この件、課題にして"
    assert strip_mentions(text) == "この件、課題にして"


def test_strip_multiple_mentions():
    text = "<at>ToPal</at> <at>User1</at> この件お願い"
    assert strip_mentions(text) == "この件お願い"


def test_strip_mention_with_html():
    text = "<p><at>ToPal</at> PROJ-123の優先度上げて</p>"
    assert strip_mentions(text) == "PROJ-123の優先度上げて"


def test_strip_no_mention():
    text = "普通のテキスト"
    assert strip_mentions(text) == "普通のテキスト"


def test_strip_empty():
    assert strip_mentions("") == ""


def test_extract_text_from_payload():
    payload = {"text": "<at>ToPal</at> タスク作って"}
    assert extract_text(payload) == "タスク作って"


def test_extract_text_missing_key():
    payload = {}
    assert extract_text(payload) == ""

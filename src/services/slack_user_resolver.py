"""Slack User IDから表示名を取得するモジュール。"""

import logging

import requests

from src.services import ssm_client

logger = logging.getLogger(__name__)

_SLACK_USERS_INFO_URL = "https://slack.com/api/users.info"

_user_cache: dict[str, str] = {}


def resolve_display_name(user_id: str) -> str:
    """Slack User IDから表示名を取得する。

    Args:
        user_id: SlackユーザーID（例: U09C8CWHVA7）

    Returns:
        表示名（取得失敗時はuser_idをそのまま返す）
    """
    if not user_id:
        return "不明"

    if user_id in _user_cache:
        return _user_cache[user_id]

    token = ssm_client.get_slack_bot_token()

    try:
        resp = requests.get(
            _SLACK_USERS_INFO_URL,
            params={"user": user_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            logger.warning("Slack users.info APIエラー: %s", data.get("error"))
            return user_id

        user = data["user"]
        # display_name → real_name → name の優先順で取得
        name = (
            user.get("profile", {}).get("display_name")
            or user.get("real_name")
            or user.get("name")
            or user_id
        )

        _user_cache[user_id] = name
        logger.info("Slackユーザー名を解決: %s → %s", user_id, name)
        return name

    except requests.RequestException:
        logger.exception("Slack users.info APIの呼び出しに失敗: %s", user_id)
        return user_id

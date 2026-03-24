"""AWS SSM Parameter Storeからシークレット・設定値を取得するモジュール。"""

import os

import boto3


_cache = {}


def _get_ssm_client():
    """SSMクライアントを生成する。ローカルではLocalStackに接続する。"""
    kwargs = {"region_name": os.environ.get("AWS_REGION", "ap-northeast-1")}
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("ssm", **kwargs)


def _get_parameter(name: str, decrypt: bool = True) -> str:
    """SSMパラメータを取得する（キャッシュ付き）。

    Args:
        name: パラメータのフルパス
        decrypt: SecureStringを復号するかどうか

    Returns:
        パラメータ値
    """
    if name in _cache:
        return _cache[name]

    client = _get_ssm_client()
    response = client.get_parameter(Name=name, WithDecryption=decrypt)
    value = response["Parameter"]["Value"]

    _cache[name] = value
    return value


def _prefix():
    return os.environ.get("SSM_PREFIX", "/topal")


def get_anthropic_api_key() -> str:
    """Anthropic APIキーを取得する。"""
    return _get_parameter(f"{_prefix()}/anthropic_api_key")


def get_claude_model() -> str:
    """Claude モデル名を取得する。"""
    return _get_parameter(f"{_prefix()}/claude_model", decrypt=False)


def get_teams_webhook_secret() -> str:
    """Teams Webhookシークレットを取得する。"""
    return _get_parameter(f"{_prefix()}/teams_webhook_secret")


def get_teams_incoming_webhook_url() -> str:
    """Teams Incoming Webhook URLを取得する。"""
    return _get_parameter(f"{_prefix()}/teams_incoming_webhook_url", decrypt=False)


def get_backlog_api_key(project_key: str) -> str:
    """プロジェクトのBacklog APIキーをSSMから取得する。

    Args:
        project_key: Backlogプロジェクトキー（例: NOHARATEST）

    Returns:
        Backlog APIキー文字列
    """
    return _get_parameter(f"{_prefix()}/{project_key}/backlog_api_key")


def get_backlog_space_url(project_key: str) -> str:
    """プロジェクトのBacklogスペースURLをSSMから取得する。

    Args:
        project_key: Backlogプロジェクトキー（例: NOHARATEST）

    Returns:
        BacklogスペースURL（例: https://comthink06.backlog.com）
    """
    return _get_parameter(f"{_prefix()}/{project_key}/backlog_space_url", decrypt=False)


def clear_cache():
    """キャッシュをクリアする（テスト用）。"""
    _cache.clear()

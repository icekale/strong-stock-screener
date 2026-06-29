from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.notification_channels import (
    NotificationChannelConfig,
    NotificationSettings,
    send_notification_message,
)
from app.services.runtime_settings import SettingsUpdate, load_runtime_settings, save_runtime_settings


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeHttpClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        return FakeResponse()


class FakeSmtpClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def send(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        recipients: list[str],
        subject: str,
        body: str,
        use_tls: bool,
    ) -> None:
        self.sent.append(
            {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "sender": sender,
                "recipients": recipients,
                "subject": subject,
                "body": body,
                "use_tls": use_tls,
            }
        )


def test_runtime_settings_saves_notification_channels(tmp_path: Path) -> None:
    path = tmp_path / "runtime_config.json"

    save_runtime_settings(
        path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.org",
            ifind_base_url="https://api-mcp.51ifind.com:8643",
            ifind_service_id="hexin-ifind-ds-stock-mcp",
            provider_timeout_seconds=12,
            notification_channels=[
                NotificationChannelConfig(
                    id="wechat-main",
                    type="wechat_work",
                    name="企业微信",
                    enabled=True,
                    webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x",
                )
            ],
        ),
    )

    loaded = load_runtime_settings(path)

    assert loaded.notification_channels[0].id == "wechat-main"
    assert loaded.notification_channels[0].type == "wechat_work"
    assert loaded.notification_channels[0].webhook_url.endswith("key=x")


def test_send_notification_message_posts_wechat_work_payload() -> None:
    http_client = FakeHttpClient()
    result = send_notification_message(
        NotificationSettings(
            channels=[
                NotificationChannelConfig(
                    id="wechat-main",
                    type="wechat_work",
                    name="企业微信",
                    enabled=True,
                    webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x",
                )
            ]
        ),
        title="短线情绪提醒",
        message_text="测试内容",
        channel_ids=["wechat-main"],
        http_client=http_client,
    )

    assert result.results[0].status == "success"
    assert http_client.posts[0]["url"] == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x"
    assert http_client.posts[0]["json"] == {"msgtype": "text", "text": {"content": "短线情绪提醒\n\n测试内容"}}


def test_send_notification_message_sends_email_payload() -> None:
    smtp_client = FakeSmtpClient()
    result = send_notification_message(
        NotificationSettings(
            channels=[
                NotificationChannelConfig(
                    id="mail-main",
                    type="email",
                    name="邮件",
                    enabled=True,
                    smtp_host="smtp.example.com",
                    smtp_port=587,
                    smtp_username="bot@example.com",
                    smtp_password="secret",
                    smtp_sender="bot@example.com",
                    smtp_recipients=["a@example.com", "b@example.com"],
                )
            ]
        ),
        title="短线情绪提醒",
        message_text="测试内容",
        channel_ids=["mail-main"],
        smtp_client=smtp_client,
    )

    assert result.results[0].status == "success"
    assert smtp_client.sent[0]["host"] == "smtp.example.com"
    assert smtp_client.sent[0]["subject"] == "短线情绪提醒"
    assert smtp_client.sent[0]["body"] == "测试内容"


def test_notification_send_api_uses_runtime_config(tmp_path: Path) -> None:
    path = tmp_path / "runtime_config.json"
    save_runtime_settings(
        path,
        SettingsUpdate(
            candidate_provider="recent_limit_up",
            kline_provider="tickflow",
            quote_provider="tickflow",
            tickflow_base_url="https://api.tickflow.org",
            ifind_base_url="https://api-mcp.51ifind.com:8643",
            ifind_service_id="hexin-ifind-ds-stock-mcp",
            provider_timeout_seconds=12,
            notification_channels=[
                NotificationChannelConfig(
                    id="wechat-main",
                    type="wechat_work",
                    name="企业微信",
                    enabled=True,
                    webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=x",
                )
            ],
        ),
    )
    app.state.runtime_config_path = path
    app.state.notification_http_client = FakeHttpClient()
    try:
        response = TestClient(app).post(
            "/api/notifications/send",
            json={
                "title": "短线情绪提醒",
                "message_text": "测试内容",
                "channel_ids": ["wechat-main"],
            },
        )
    finally:
        delattr(app.state, "runtime_config_path")
        delattr(app.state, "notification_http_client")

    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "success"

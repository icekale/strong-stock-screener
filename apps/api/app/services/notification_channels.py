from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field


NotificationChannelType = Literal["wechat_work", "feishu", "telegram", "email"]
NotificationSendStatus = Literal["success", "failed", "disabled", "not_found"]


class NotificationChannelConfig(BaseModel):
    id: str
    type: NotificationChannelType
    name: str
    enabled: bool = True
    webhook_url: str | None = None
    bot_token: str | None = None
    chat_id: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_recipients: list[str] = Field(default_factory=list)
    smtp_use_tls: bool = True


class NotificationSettings(BaseModel):
    channels: list[NotificationChannelConfig] = Field(default_factory=list)


class NotificationSendResultItem(BaseModel):
    channel_id: str
    channel_name: str
    type: NotificationChannelType | None = None
    status: NotificationSendStatus
    detail: str


class NotificationSendResult(BaseModel):
    results: list[NotificationSendResultItem] = Field(default_factory=list)


class SmtpClient(Protocol):
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
        ...


class DefaultSmtpClient:
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
        message = EmailMessage()
        message["From"] = sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if use_tls:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(message)


def public_notification_settings(settings: NotificationSettings) -> dict[str, object]:
    return {
        "channels": [
            {
                "id": channel.id,
                "type": channel.type,
                "name": channel.name,
                "enabled": channel.enabled,
                "webhook_configured": bool(channel.webhook_url),
                "bot_token_configured": bool(channel.bot_token),
                "chat_id_configured": bool(channel.chat_id),
                "smtp_host": channel.smtp_host or "",
                "smtp_port": channel.smtp_port,
                "smtp_username": channel.smtp_username or "",
                "smtp_sender": channel.smtp_sender or "",
                "smtp_recipients": channel.smtp_recipients,
                "smtp_use_tls": channel.smtp_use_tls,
            }
            for channel in settings.channels
        ]
    }


def send_notification_message(
    settings: NotificationSettings,
    title: str,
    message_text: str,
    channel_ids: list[str] | None = None,
    http_client: object | None = None,
    smtp_client: SmtpClient | None = None,
) -> NotificationSendResult:
    selected = _selected_channels(settings.channels, channel_ids)
    http = http_client or httpx.Client(timeout=20)
    smtp = smtp_client or DefaultSmtpClient()
    results: list[NotificationSendResultItem] = []
    for channel in selected:
        results.append(_send_one(channel, title, message_text, http, smtp))
    if channel_ids:
        found_ids = {channel.id for channel in selected}
        for channel_id in channel_ids:
            if channel_id not in found_ids:
                results.append(
                    NotificationSendResultItem(
                        channel_id=channel_id,
                        channel_name=channel_id,
                        type=None,
                        status="not_found",
                        detail="通知渠道不存在",
                    )
                )
    return NotificationSendResult(results=results)


def _selected_channels(
    channels: list[NotificationChannelConfig],
    channel_ids: list[str] | None,
) -> list[NotificationChannelConfig]:
    if not channel_ids:
        return channels
    wanted = set(channel_ids)
    return [channel for channel in channels if channel.id in wanted]


def _send_one(
    channel: NotificationChannelConfig,
    title: str,
    message_text: str,
    http_client: object,
    smtp_client: SmtpClient,
) -> NotificationSendResultItem:
    if not channel.enabled:
        return _result(channel, "disabled", "渠道已禁用")
    try:
        if channel.type == "wechat_work":
            _send_wechat_work(channel, title, message_text, http_client)
        elif channel.type == "feishu":
            _send_feishu(channel, title, message_text, http_client)
        elif channel.type == "telegram":
            _send_telegram(channel, title, message_text, http_client)
        elif channel.type == "email":
            _send_email(channel, title, message_text, smtp_client)
    except Exception as exc:
        return _result(channel, "failed", str(exc))
    return _result(channel, "success", "发送成功")


def _send_wechat_work(
    channel: NotificationChannelConfig,
    title: str,
    message_text: str,
    http_client: object,
) -> None:
    if not channel.webhook_url:
        raise ValueError("企业微信 webhook 未配置")
    response = http_client.post(
        channel.webhook_url,
        json={"msgtype": "text", "text": {"content": f"{title}\n\n{message_text}"}},
    )
    response.raise_for_status()


def _send_feishu(
    channel: NotificationChannelConfig,
    title: str,
    message_text: str,
    http_client: object,
) -> None:
    if not channel.webhook_url:
        raise ValueError("飞书 webhook 未配置")
    response = http_client.post(
        channel.webhook_url,
        json={"msg_type": "text", "content": {"text": f"{title}\n\n{message_text}"}},
    )
    response.raise_for_status()


def _send_telegram(
    channel: NotificationChannelConfig,
    title: str,
    message_text: str,
    http_client: object,
) -> None:
    if not channel.bot_token or not channel.chat_id:
        raise ValueError("Telegram bot token 或 chat id 未配置")
    response = http_client.post(
        f"https://api.telegram.org/bot{channel.bot_token}/sendMessage",
        json={"chat_id": channel.chat_id, "text": f"{title}\n\n{message_text}"},
    )
    response.raise_for_status()


def _send_email(
    channel: NotificationChannelConfig,
    title: str,
    message_text: str,
    smtp_client: SmtpClient,
) -> None:
    if not channel.smtp_host or not channel.smtp_sender or not channel.smtp_recipients:
        raise ValueError("邮件 SMTP 主机、发件人或收件人未配置")
    smtp_client.send(
        host=channel.smtp_host,
        port=channel.smtp_port,
        username=channel.smtp_username or "",
        password=channel.smtp_password or "",
        sender=channel.smtp_sender,
        recipients=channel.smtp_recipients,
        subject=title,
        body=message_text,
        use_tls=channel.smtp_use_tls,
    )


def _result(
    channel: NotificationChannelConfig,
    status: NotificationSendStatus,
    detail: str,
) -> NotificationSendResultItem:
    return NotificationSendResultItem(
        channel_id=channel.id,
        channel_name=channel.name,
        type=channel.type,
        status=status,
        detail=detail,
    )

"""可插拔通知统一分发器 (Notification Dispatcher)。"""

import logging
from typing import Dict

from ...models import User
from .base import BaseNotificationChannel
from .email_channel import EmailNotificationChannel

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self):
        self._channels: Dict[str, BaseNotificationChannel] = {}
        # 默认注册邮箱渠道
        self.register(EmailNotificationChannel())

    def register(self, channel: BaseNotificationChannel) -> None:
        self._channels[channel.name] = channel

    def get_channel(self, name: str) -> BaseNotificationChannel | None:
        return self._channels.get(name)

    def dispatch(
        self,
        user: User,
        subject: str,
        content: str,
        channels: list[str] | None = None,
        is_html: bool = True,
        extra_data: dict | None = None,
    ) -> dict[str, tuple[bool, str | None]]:
        """向指定的渠道列表（默认 ['email']）投递通知。"""
        target_channels = channels or ["email"]
        results = {}

        for ch_name in target_channels:
            channel = self._channels.get(ch_name)
            if not channel:
                results[ch_name] = (False, f"未知的通知渠道: {ch_name}")
                continue

            try:
                ok, err = channel.send(
                    user=user,
                    subject=subject,
                    content=content,
                    is_html=is_html,
                    extra_data=extra_data,
                )
                results[ch_name] = (ok, err)
                if not ok:
                    logger.warning(
                        f"Notification dispatch to {user.email} via {ch_name} failed: {err}"
                    )
            except Exception as e:
                logger.exception(f"Unexpected error in notification channel {ch_name}: {e}")
                results[ch_name] = (False, str(e))

        return results


# 全局单例分发器
dispatcher = NotificationDispatcher()

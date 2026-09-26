"""邮件通知渠道实现（基于 Resend）。"""

from ...models import User
from ..notify import send_email
from .base import BaseNotificationChannel


class EmailNotificationChannel(BaseNotificationChannel):
    name = "email"

    def send(
        self,
        user: User,
        subject: str,
        content: str,
        is_html: bool = True,
        extra_data: dict | None = None,
    ) -> tuple[bool, str | None]:
        if not user.email:
            return False, "用户未绑定有效电子邮箱"

        # 如果 content 并非 HTML，则构造基础 HTML
        html = content if is_html else f"<pre style='font-family:sans-serif;'>{content}</pre>"
        return send_email(to=user.email, subject=subject, html=html)

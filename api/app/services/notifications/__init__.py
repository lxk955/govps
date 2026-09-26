"""GoVPS 可插拔通知服务模块。"""

from .base import BaseNotificationChannel
from .dispatcher import NotificationDispatcher, dispatcher
from .email_channel import EmailNotificationChannel
from .expiration_checker import (
    check_expiring_nodes,
    generate_renewal_token,
    render_expiration_email,
    send_test_expiration_email,
    verify_renewal_token,
)

__all__ = [
    "BaseNotificationChannel",
    "EmailNotificationChannel",
    "NotificationDispatcher",
    "dispatcher",
    "check_expiring_nodes",
    "generate_renewal_token",
    "render_expiration_email",
    "send_test_expiration_email",
    "verify_renewal_token",
]

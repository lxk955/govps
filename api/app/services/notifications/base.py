"""可插拔通知渠道基类定义。"""

from abc import ABC, abstractmethod

from ...models import User


class BaseNotificationChannel(ABC):
    """通知渠道抽象基类。后续新增 Webhook、Telegram、Bark 时只需继承此类并注册到 Dispatcher。"""

    name: str

    @abstractmethod
    def send(
        self,
        user: User,
        subject: str,
        content: str,
        is_html: bool = True,
        extra_data: dict | None = None,
    ) -> tuple[bool, str | None]:
        """向目标用户投递通知。
        
        返回: (是否成功, 错误信息/None)
        """
        pass

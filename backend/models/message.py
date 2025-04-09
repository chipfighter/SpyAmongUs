"""
model: Message
"""
from pydantic import BaseModel
import time

class Message(BaseModel):
    """消息模型"""
    timestamp: int = int(time.time() * 1000)  # 时间戳 (Unix 时间戳, 毫秒)
    user_id: str            # 发送者ID
    username: str           # 发送者用户名
    content: str            # 消息内容
    is_system: bool = False # 是否为系统消息
    round: int = 0  # 当前消息所处的局数

    @classmethod
    def create_user_message(cls, user_id: str, username: str, content: str) -> 'Message':
        """创建用户消息"""
        return cls(
            timestamp=int(time.time() * 1000),  # 使用 Unix 时间戳
            user_id=user_id,
            username=username,
            content=content,
            is_system=False,
            round=0
        )

    @classmethod
    def create_system_message(cls, content: str) -> 'Message':
        """创建系统消息"""
        return cls(
            timestamp=int(time.time() * 1000),  # 使用 Unix 时间戳
            user_id="system",
            username="System",
            content=content,
            is_system=True,
            round=0
        )

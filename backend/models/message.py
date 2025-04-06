"""
model: Message
"""
from pydantic import BaseModel
import time

class Message(BaseModel):
    """消息模型"""
    id: str                 # 消息ID
    room_id: str            # 房间ID
    user_id: str            # 发送者ID
    username: str           # 发送者用户名
    content: str            # 消息内容
    timestamp: int = int(time.time() * 1000)    # 时间戳
    is_system: bool = False                     # 是否为系统消息

    @classmethod
    def create_user_message(cls, room_id: str, user_id: str, username: str, content: str) -> 'Message':
        """创建用户消息"""
        return cls(
            id=f"msg_{int(time.time() * 1000)}",
            room_id=room_id,
            user_id=user_id,
            username=username,
            content=content
        )

    @classmethod
    def create_system_message(cls, room_id: str, content: str) -> 'Message':
        """创建系统消息"""
        return cls(
            id=f"sys_{int(time.time() * 1000)}",
            room_id=room_id,
            user_id="system",
            username="System",
            content=content,
            is_system=True
        )
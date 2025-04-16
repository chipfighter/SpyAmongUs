"""
model: Message

Notes:
    一般传输按照dict类型直接传输即可
"""

from pydantic import BaseModel
from typing import Optional, Dict, List
import time

class Message(BaseModel):
    """
    消息模型

    Notes:
        前端
    """
    timestamp: int = int(time.time() * 1000)  # 时间戳 (Unix 时间戳, 毫秒)
    user_id: str            # 发送者ID
    username: str          # 发送者用户名
    content: str            # 消息内容
    is_system: bool = False # 是否为系统消息
    round: str = "0"        # 所属回合（改为字符串类型）【如果是"0"默认游戏没有开始，游戏开始的回合为"round_x"】

    mentions: Optional[List[Dict[str, str]]] = []  # 包含被@的用户的信息
    ai_type: Optional[str] = None  # 被@的AI类型

    @classmethod
    def create_user_message(cls, user_id: str, username: str, content: str) -> 'Message':
        """创建用户消息"""
        return cls(
            timestamp=int(time.time() * 1000),
            user_id=user_id,
            username=username,  # 使用username
            content=content,
            is_system=False,
            round="0"  # 使用字符串
        )

    @classmethod
    def create_system_message(cls, content: str) -> 'Message':
        """创建系统消息"""
        return cls(
            timestamp=int(time.time() * 1000),
            user_id="system",
            username="System",  # 使用username
            content=content,
            is_system=True,
            round="0"  # 使用字符串
        )
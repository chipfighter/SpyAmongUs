"""
model: Room
"""
from pydantic import BaseModel
from typing import Dict, Set, Optional, List, Any
import uuid
import random
import string
import time


class Room(BaseModel):
    id: str                 # 房间ID（唯一标识）
    name: str               # 房间名
    host_id: str            # 房主ID
    invitation_code: str    # 邀请码
    is_public: bool = True  # 房间是否公开（与邀请码绑定）

    # 房间状态
    room_status: str = "waiting"  # 房间状态: waiting(等待中), playing(游戏中), finished(已结束)

    # 用户相关的信息记录
    users: Set[str] = set()        # 房间内存在的所有用户ID
    leaving_in_game_users: Set[str] = set()  # 已离开但游戏中的用户ID（等待游戏结束自动清理释放）
    ready_users: Set[str] = set()  # 已准备用户ID（所有用户准备后自动开始）

    timer: float = 0.0    # 状态计时器，记录上次状态变更的时间戳，用于追踪房间状态持续时间

    def dict(self, **kwargs) -> Dict[str, Any]:
        """重写dict将集合转变成列表（Redis需要）"""
        room_dict = super().dict(**kwargs)
        
        # 将集合字段转换为列表
        set_fields = ["users", "leaving_in_game_users", "ready_users"]
        for field in set_fields:
            if field in room_dict and isinstance(room_dict[field], set):
                room_dict[field] = list(room_dict[field])
        
        # 确保布尔值是字符串
        room_dict["is_public"] = str(room_dict["is_public"]).lower()
        
        return room_dict

    @classmethod
    def create_room(cls, name: str, host_id: str, is_public: bool = True):
        """创建房间

        Args:
            name: 房间名
            host_id: 创建房间的房主id
            is_public: 是否公开

        Returns:
            封装完的class Room
        """

        # 生成6位随机邀请码
        invitation_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        return cls(
            id=str(uuid.uuid4()),
            name=name,
            host_id=host_id,
            invitation_code=invitation_code,
            is_public=is_public,
            timer=time.time()  # 初始化时间戳为当前时间
        )
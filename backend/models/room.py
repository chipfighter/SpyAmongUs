"""
model: Room
"""
import time

from pydantic import BaseModel, Field
from typing import Dict, Optional, Any
import random
import string
from config import (
    GAME_STATUS_WAITING,
    MIN_PLAYERS, MIN_SPY_COUNT,
    MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME
)


class Room(BaseModel):
    """
    房间核心模型
    
    仅保留基础房间信息和游戏配置，其他数据（用户列表、消息、投票等）
    通过invite_code在Redis中单独存储
    """
    # 基本房间信息（创建时必须的）
    invite_code: str
    room_name: str
    host_id: str
    is_public: bool = True
    
    # 游戏配置（创建时设置）
    total_players: int = MIN_PLAYERS
    spy_count: int = MIN_SPY_COUNT
    max_rounds: int = MAX_ROUNDS
    speak_time: int = MAX_SPEAK_TIME
    last_words_time: int = MAX_LAST_WORDS_TIME
    llm_free: bool = False

    # 房间状态（游戏开始时初始化）
    status: str = GAME_STATUS_WAITING
    current_round: int = 0
    current_phase: str = ""

    # 游戏数据（游戏开始时初始化）
    god_id: Optional[str] = None
    word_civilian: Optional[str] = None
    word_spy: Optional[str] = None

    # 秘密聊天室（游戏开始时初始化）
    secret_chat_active: bool = False

    # 时间相关
    created_at: int = int(time.time() * 1000)
    last_active: int = int(time.time() * 1000)

    def dict(self, **kwargs) -> Dict[str, Any]:
        """将Python对象转化为适合Redis存储的格式"""
        room_dict = super().dict(**kwargs)

        # 确保布尔值是字符串
        bool_fields = ["is_public", "llm_free", "secret_chat_active"]
        for field in bool_fields:
            if field in room_dict:
                room_dict[field] = str(room_dict[field]).lower()    # bool类型全部转变为小写字符串！

        # 处理空值
        for key, value in room_dict.items():
            if value == "" or value == "null":
                room_dict[key] = None

        return room_dict


    @classmethod
    def create_room(cls, room_name: str, host_id: str, is_public: bool = True,
                    total_players: int = MIN_PLAYERS, spy_count: int = MIN_SPY_COUNT,
                    max_rounds: int = MAX_ROUNDS, speak_time: int = MAX_SPEAK_TIME,
                    last_words_time: int = MAX_LAST_WORDS_TIME, llm_free: bool = False) -> 'Room':
        """创建新房间

        Args:
            room_name: 房间名称
            host_id: 房主ID
            is_public: 是否公开
            total_players: 总玩家数
            spy_count: 卧底数量
            max_rounds: 最大回合数
            speak_time: 发言时间（秒）
            last_words_time: 遗言时间（秒）
            llm_free: 是否自由发言

        Returns:
            Room: 新创建的房间对象
        """
        # 生成8位不重复邀请码
        invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # 创建时间戳
        timestamp = int(time.time() * 1000)

        # 创建房间实例 - 只初始化基本信息，游戏相关数据在游戏开始时初始化
        room = cls(
            invite_code=invite_code,
            room_name=room_name,
            host_id=host_id,
            is_public=is_public,
            total_players=total_players,
            spy_count=spy_count,
            max_rounds=max_rounds,
            speak_time=speak_time,
            last_words_time=last_words_time,
            llm_free=llm_free,
            status=GAME_STATUS_WAITING,
            created_at=timestamp,
            last_active=timestamp
        )

        return room
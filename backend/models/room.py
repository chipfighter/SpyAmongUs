"""
model: Room
"""
import time

from pydantic import BaseModel, Field
from typing import Dict, Set, Optional, List, Any, Union
import random
import string
from config import (
    GAME_STATUS_WAITING,
    MIN_PLAYERS, MIN_SPY_COUNT,
    MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME
)
from models.message import Message


class Room(BaseModel):
    # 原有字段都应保留
    invite_code: str
    name: str
    host_id: str
    is_public: bool = True
    users: Set[str] = Field(default_factory=set)  # 应该保留

    # 游戏配置
    total_players: int = MIN_PLAYERS
    spy_count: int = MIN_SPY_COUNT
    max_rounds: int = MAX_ROUNDS
    speak_time: int = MAX_SPEAK_TIME
    last_words_time: int = MAX_LAST_WORDS_TIME
    llm_free: bool = False

    # 房间状态
    status: str = GAME_STATUS_WAITING
    current_round: int = 0
    current_phase: str = ""

    # 游戏数据
    god_id: Optional[str] = None
    word_civilian: str = None
    word_spy: str = None

    # 用户相关
    ready_users: Set[str] = Field(default_factory=set)
    alive_players: Set[str] = Field(default_factory=set)
    roles: Dict[str, str] = Field(default_factory=dict)

    # 投票历史
    votes: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # 秘密聊天室
    secret_chat_active: bool = False
    secret_chat_votes: Dict[str, bool] = Field(default_factory=dict)

    # 消息相关
    messages: List[Message] = Field(default_factory=list)  # 房间内所有消息
    secret_chat_messages: List[Message] = Field(default_factory=list)  # 秘密聊天消息

    # 时间相关
    created_at: int = int(time.time() * 1000)
    last_active: int = int(time.time() * 1000)

    def dict(self, **kwargs) -> Dict[str, Any]:
        """将redis读取出来的数据转化成Python可以处理的数据

        Notes:
            Set -> List, Type Confirm: bool, null -> None
        """
        room_dict = super().dict(**kwargs)

        # 将集合字段转换为列表
        set_fields = ["users", "ready_users", "alive_players"]
        for field in set_fields:
            if field in room_dict and isinstance(room_dict[field], set):
                room_dict[field] = list(room_dict[field])

        # 确保布尔值是字符串
        bool_fields = ["is_public", "llm_free", "secret_chat_active"]
        for field in bool_fields:
            if field in room_dict:
                room_dict[field] = str(room_dict[field]).lower()

        # 处理空值
        for key, value in room_dict.items():
            if value == "" or value == "null":
                room_dict[key] = None

        return room_dict


    @classmethod
    def create_room(cls, name: str, host_id: str, is_public: bool = True,
                    total_players: int = MIN_PLAYERS, spy_count: int = MIN_SPY_COUNT,
                    max_rounds: int = MAX_ROUNDS, speak_time: int = MAX_SPEAK_TIME,
                    last_words_time: int = MAX_LAST_WORDS_TIME, llm_free: bool = False) -> 'Room':
        """创建新房间

        Args:
            name: 房间名称
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

        # 创建房间实例
        room = cls(
            invite_code=invite_code,
            name=name,
            host_id=host_id,
            is_public=is_public,
            total_players=total_players,
            spy_count=spy_count,
            max_rounds=max_rounds,
            speak_time=speak_time,
            last_words_time=last_words_time,
            llm_free=llm_free,
            status=GAME_STATUS_WAITING,
            current_round=0,
            current_phase="",
            god_id=None,
            word_civilian="",
            word_spy="",
            users=set(),
            ready_users=set(),
            alive_players=set(),
            roles={},
            votes={},
            secret_chat_active=False,
            secret_chat_votes={},
            messages=[],
            secret_chat_messages=[],
            created_at=timestamp,
            last_active=timestamp
        )

        return room
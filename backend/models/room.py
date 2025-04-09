"""
model: Room
"""
import time

from pydantic import BaseModel, Field
from typing import Dict, Set, Optional, List, Any, Union
import uuid
import random
import string
from datetime import datetime
from config import (
    GAME_STATUS_WAITING, GAME_STATUS_PLAYING,
    GAME_PHASE_SPEAKING, ROLE_CIVILIAN, ROLE_SPY, MIN_PLAYERS, MIN_SPY_COUNT, MAX_PLAYERS,
    MAX_SPY_RATIO, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME
)
from models.message import Message


class Room(BaseModel):
    invite_code: str    # 邀请码（唯一标识）
    name: str               # 房间名
    host_id: str            # 房主ID
    is_public: bool = True      # 房间是否公开（与邀请码绑定）
    users: Set[str] = Field(default_factory=set)  # 房间内存在的所有用户ID

    # 游戏配置 (由房主设置)
    total_players: int = MIN_PLAYERS      # 总玩家数
    spy_count: int = MIN_SPY_COUNT        # 卧底数量
    max_rounds: int = MAX_ROUNDS         # 最大回合数
    speak_time: int = MAX_SPEAK_TIME        # 发言时间
    last_words_time: int = MAX_LAST_WORDS_TIME   # 遗言时间
    llm_free: bool = False      # 是否允许大模型自由聊天广播

    # 房间状态: waiting(等待)、playing(游戏中)
    status: str = GAME_STATUS_WAITING
    # 游戏状态
    current_round: int = 0      # 当前回合 (0表示未开始)
    current_phase: str = ""     # 当前阶段 (speaking/voting/secret_chat)

    # 游戏数据
    god_id: Optional[str] = None  # 上帝ID，如果为None则使用场外AI
    words: Dict[str, str] = Field(default_factory=dict)  # {"civilian": "平民词", "spy": "卧底词"}

    # 用户相关
    ready_users: Set[str] = Field(default_factory=set)  # 已准备的用户ID
    alive_players: Set[str] = Field(default_factory=set)  # 存活玩家ID
    roles: Dict[str, str] = Field(default_factory=dict)  # 当前的用户id对应的不同角色：{"user_id": "god/civilian/spy"}

    # 投票历史
    votes: Dict[str, Dict[str, str]] = Field(default_factory=dict)  # {"round_1": {"voter_id": "target_id"}}

    # 消息列表
    messages: List[Message] = []    # 房间内所有消息对象的列表

    # 秘密聊天室
    secret_chat_active: bool = False  # 秘密聊天室是否激活
    secret_chat_votes: Dict[str, bool] = Field(default_factory=dict)  # {"spy_id": true/false}
    secret_chat_messages: List[Message] = []    # 秘密小房间的消息列表
    
    # 时间相关
    created_at: int = int(time.time() * 1000)   # 创建时间
    last_active: int = int(time.time() * 1000)   # 最后活动时间

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
        # 生成6位不重复邀请码
        while True:
            invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not redis_client.exists(f"{ROOM_CODE_KEY_PREFIX}{invite_code}"):
                break

        return cls(
            invite_code=invite_code,
            name=name,
            host_id=host_id,
            is_public=is_public,
            total_players=total_players,
            spy_count=spy_count,
            max_rounds=max_rounds,
            speak_time=speak_time,
            last_words_time=last_words_time,
            llm_free=llm_free
        )

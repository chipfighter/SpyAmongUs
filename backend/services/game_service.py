"""
services: game_service

Description:
    与游戏内部进行逻辑相关的逻辑，主要实现游戏相关的逻辑

Notes:
    游戏初始化、角色分配、游戏进程管理等核心功能
"""
import asyncio
import random
import logging
import time
import uuid
import gc
import weakref
import sys
import json
from typing import Dict, List, Any, Optional

from config import ROOM_POLL_STATE_KEY_PREFIX

logger = logging.getLogger(__name__)

class GameService:
    def __init__(self, redis_client=None, websocket_manager=None):
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        if redis_client and websocket_manager:
            logger.info("GameService已初始化")
    
    async def poll_god_role(self, invite_code: str) -> None:
        """
        轮询广播玩家是否愿意担任上帝角色
        普通用户和正在询问的用户消息不一致
        
        Args:
            invite_code: 房间邀请码
        """
        if not self.redis_client or not self.websocket_manager:
            logger.error("GameService未初始化，无法执行轮询")
            return
            
        # 创建追踪ID
        trace_id = f"poll_{uuid.uuid4().hex[:6]}_{int(time.time())}"
        
        try:
            # 从Redis获取轮询状态，如果存在
            poll_state = await self.redis_client.get_poll_state(invite_code)
            
            # 如果是新轮询或者没有轮询状态，初始化状态
            if not poll_state:
                # 获取房间内所有玩家
                players = await self.redis_client.get_room_users(invite_code)
                if not players:
                    logger.warning(f"[{trace_id}] 房间 {invite_code} 没有玩家，无法轮询上帝角色")
                    return
                
                # 转换为列表以确保支持shuffle操作
                players = list(players)
                
                # 进行完全随机打乱，不受原始顺序影响
                random.shuffle(players)
                logger.info(f"[{trace_id}] 房间 {invite_code} 轮询上帝角色，随机顺序: {players}")
                
                # 初始化轮询状态并存储到Redis
                poll_state = {
                    "current_index": 0,
                    "player_list": players,
                    "trace_id": trace_id
                }
                
                # 将状态存储到Redis
                await self.redis_client.set_poll_state(invite_code, poll_state)
                
                # 获取当前要询问的玩家
                current_player = players[0]
            else:
                # 获取下一个要询问的玩家
                current_index = poll_state["current_index"]
                player_list = poll_state["player_list"]

                # 检查是否已经询问完所有玩家
                if current_index >= len(player_list):
                    # TODO: 调用AI转发层分发词语
                    # 清理轮询状态
                    await self.redis_client.delete_poll_state(invite_code)
                    return
                
                # 获取当前要询问的玩家
                current_player = player_list[current_index]
                
                # 更新追踪ID
                poll_state["trace_id"] = trace_id
                await self.redis_client.set_poll_state(invite_code, poll_state)
            
            # 获取玩家信息
            player_data = await self.redis_client.hgetall(f"user:{current_player}")
            username = player_data.get("username", "未知玩家")
            
            # 定义轮询超时时间
            timeout_seconds = 7
            
            # 准备广播任务
            broadcast_tasks = []
            
            # 1. 向其他用户广播当前询问状态消息
            all_players_set = set(poll_state["player_list"])
            other_users = all_players_set - {current_player}
            if other_users:
                broadcast_tasks.append(
                    self.websocket_manager.broadcast_message(
                        invite_code=invite_code,
                        message={
                            "type": "god_role_inquiry_status",
                            "current_user": current_player,
                            "username": username,
                            "timeout": timeout_seconds,
                            "message": f"正在询问 {username} 是否愿意担任上帝...",
                            "total_players": len(poll_state["player_list"]),
                            "current_index": poll_state["current_index"] + 1
                        },
                        is_special=True,
                        target_users=other_users
                    )
                )
            
            # 2. 向当前玩家发送询问
            broadcast_tasks.append(
                self.websocket_manager.broadcast_message(
                    invite_code=invite_code,
                    message={
                        "type": "god_role_inquiry",
                        "timeout": timeout_seconds,
                        "message": "您愿意担任本局游戏的上帝吗？"
                    },
                    is_special=True,
                    target_users={current_player}
                )
            )
            
            # 并行执行所有广播任务
            await asyncio.gather(*broadcast_tasks)
            
        except Exception as e:
            logger.error(f"[{trace_id}] 轮询上帝角色异常: {str(e)}", exc_info=True)
            # 清理轮询状态
            await self.redis_client.delete_poll_state(invite_code)
    
    async def handle_god_response(self, user_id: str, message: Dict[str, Any]) -> None:
        """
        处理玩家对上帝角色询问的回应
        
        Args:
            user_id: 玩家ID
            message: 消息内容，包含accept字段表示是否接受
        """
        if not self.redis_client or not self.websocket_manager:
            logger.error("GameService未初始化，无法处理玩家响应")
            return
            
        # 创建追踪ID
        response_trace_id = f"resp_{uuid.uuid4().hex[:6]}_{int(time.time())}"
        
        # 从Redis获取用户当前房间
        user_data = await self.redis_client.get_user(user_id)
        invite_code = user_data.get("current_room")
        
        if not invite_code:
            logger.warning(f"[{response_trace_id}] 玩家 {user_id} 没有所在房间，无法处理上帝角色响应")
            return
            
        # 从Redis获取轮询状态
        poll_state = await self.redis_client.get_poll_state(invite_code)
        
        if not poll_state:
            logger.warning(f"[{response_trace_id}] 收到玩家 {user_id} 回应，但房间 {invite_code} 没有进行中的轮询")
            return
        
        # 获取当前询问的玩家
        current_index = poll_state.get("current_index", 0)
        player_list = poll_state.get("player_list", [])
        
        if current_index >= len(player_list):
            logger.warning(f"[{response_trace_id}] 轮询索引超出范围: {current_index} >= {len(player_list)}")
            return
            
        # 获取当前用户
        current_player = player_list[current_index]
        
        # 检查是否是当前轮询的玩家
        if current_player != user_id:
            logger.warning(f"[{response_trace_id}] 收到玩家 {user_id} 回应，但当前询问的是 {current_player}")
            return
            
        # 处理玩家响应
        accept = message.get("accept", False)
        
        if accept:
            # 清理轮询状态
            await self.redis_client.delete_poll_state(invite_code)
            
            # 获取成为上帝的玩家信息
            god_player_data = await self.redis_client.hgetall(f"user:{user_id}")
            god_username = god_player_data.get("username", "未知玩家")
            
            # 准备广播任务
            broadcast_tasks = []
            
            # 获取所有玩家列表
            all_players_set = set(player_list)
            
            # 先广播god_role_assigned消息，确保所有玩家关闭询问弹窗
            broadcast_tasks.append(
                self.websocket_manager.broadcast_message(
                    invite_code=invite_code,
                    message={
                        "type": "god_role_assigned",
                        "god_user_id": user_id,
                        "username": god_username,
                        "is_ai": False
                    },
                    is_special=True
                )
            )
            
            # 等待一小段时间，确保god_role_assigned消息被处理
            await asyncio.sleep(0.5)
            
            # 其他玩家列表
            other_players = all_players_set - {user_id}
            
            # 1. 向成为上帝的玩家发送消息
            broadcast_tasks.append(
                self.websocket_manager.broadcast_message(
                    invite_code=invite_code,
                    message={
                        "type": "god_words_selection",
                        "message": "请选择双方词语。",
                        "timeout": 30  # 添加超时时间 (秒)
                    },
                    is_special=True,
                    target_users={user_id}
                )
            )
            
            # 2. 向其他玩家广播谁是上帝
            if other_players:
                broadcast_tasks.append(
                    self.websocket_manager.broadcast_message(
                        invite_code=invite_code,
                        message={
                            "type": "god_words_selection",
                            "god_user_id": user_id,
                            "username": god_username,
                            "message": f"{god_username} 正在选词。",
                            "timeout": 30  # 添加超时时间 (秒)
                        },
                        is_special=True,
                        target_users=other_players
                    )
                )
                
            # 并行执行广播任务
            if broadcast_tasks:
                await asyncio.gather(*broadcast_tasks)
                
        else:
            # 更新索引
            poll_state["current_index"] = current_index + 1
            # 更新Redis中的状态
            await self.redis_client.set_poll_state(invite_code, poll_state)
            # 继续轮询下一个玩家
            await self.poll_god_role(invite_code)


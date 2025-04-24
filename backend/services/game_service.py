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

from config import (
    ROOM_POLL_STATE_KEY_PREFIX, ROOM_KEY_PREFIX, ROOM_USERS_KEY_PREFIX, 
    ROLE_SPY, ROLE_CIVILIAN, ROLE_GOD, GAME_STATUS_PLAYING, GAME_PHASE_SPEAKING,
    MIN_PLAYERS, MIN_SPY_COUNT, MAX_SPY_RATIO, ROOM_ROLES_KEY_PREFIX, 
    ROOM_ALIVE_PLAYERS_KEY_PREFIX, USER_STATUS_PLAYING
)

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

    async def initialize_game(self, room_id: str, civilian_word: str, spy_word: str) -> Dict[str, Any]:
        """
        初始化游戏:
        1. 保存词语到Redis
        2. 补充AI玩家
        3. 随机分配角色
        4. 更新房间状态为playing+更新普通用户的状态为playing
        5. 向玩家发送角色和词语信息（根据角色类型发送不同信息）:
           - 上帝: 知道所有玩家身份和两个词语
           - 平民: 只知道自己身份和平民词语
           - 卧底: 知道自己身份、卧底词语以及其他卧底队友
        6. 广播游戏初始化完成消息
        
        Args:
            room_id: 房间ID
            civilian_word: 平民词语
            spy_word: 卧底词语
            
        Returns:
            Dict: 初始化结果，包含success和message字段
        """
        if not self.redis_client:
            logger.error("GameService未初始化Redis客户端，无法初始化游戏")
            return {"success": False, "message": "游戏服务未初始化"}
            
        try:
            # 创建追踪ID
            trace_id = f"init_{uuid.uuid4().hex[:6]}_{int(time.time())}"
            logger.info(f"[{trace_id}] 开始初始化游戏: 房间={room_id}, 平民词={civilian_word}, 卧底词={spy_word}")
            
            # 1. 保存词语到Redis
            # 获取房间信息
            room_data = await self.redis_client.get_room_basic_data(room_id)
            if not room_data:
                logger.error(f"[{trace_id}] 房间 {room_id} 不存在，无法初始化游戏")
                return {"success": False, "message": "房间不存在"}
                
            # 更新词语到房间数据
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            
            # 使用并行更新两个词语
            update_tasks = [
                self.redis_client.hset(room_key, "word_civilian", civilian_word),
                self.redis_client.hset(room_key, "word_spy", spy_word)
            ]
            await asyncio.gather(*update_tasks)
            
            logger.info(f"[{trace_id}] 词语已保存到房间 {room_id}")
            
            # 2. 获取真实玩家和补充AI玩家
            real_players = await self.redis_client.get_room_users(room_id)
            if not real_players:
                logger.error(f"[{trace_id}] 房间 {room_id} 没有玩家，无法初始化游戏")
                return {"success": False, "message": "房间没有玩家"}
            
            # 获取上帝ID
            god_id = room_data.get("god_id", "")
            
            # 计算需要多少AI玩家
            total_players = int(room_data.get("total_players", MIN_PLAYERS))
            
            # 排除上帝角色，因为上帝不参与游戏角色分配
            if god_id and god_id in real_players:
                # 移除上帝，不参与游戏
                real_players = [p for p in real_players if p != god_id]
                logger.info(f"[{trace_id}] 排除上帝 {god_id}，不参与游戏")
                
            # 补充AI玩家
            player_list = list(real_players)  # 真实玩家列表
            ai_count = max(0, total_players - len(player_list))  # 需要补充的AI数量
            
            if ai_count > 0:
                # 准备AI玩家添加任务列表
                ai_tasks = []
                
                for i in range(1, ai_count + 1):
                    ai_player_id = f"llm_player_{i}"
                    player_list.append(ai_player_id)
                    
                    # 将AI玩家添加到房间用户集合
                    ai_add_task = self.redis_client.zadd(
                        ROOM_USERS_KEY_PREFIX % room_id,
                        {ai_player_id: int(time.time() * 1000)}
                    )
                    
                    # 缓存AI玩家的用户信息到Redis
                    ai_user_data = {
                        "id": ai_player_id,
                        "username": f"AI玩家{i}",
                        "status": USER_STATUS_PLAYING,
                        "current_room": room_id,
                        "avatar_url": "/ai_avatar.png",
                        "is_ai": "true"
                    }
                    ai_cache_task = self.redis_client.cache_user(ai_player_id, ai_user_data)
                    
                    # 添加到任务列表
                    ai_tasks.extend([ai_add_task, ai_cache_task])
                
                # 并行执行所有AI玩家添加任务
                if ai_tasks:
                    await asyncio.gather(*ai_tasks)
                    
                logger.info(f"[{trace_id}] 补充了 {ai_count} 个AI玩家到房间 {room_id}")
            
            # 3. 随机分配角色
            # 计算卧底数量
            spy_count = int(room_data.get("spy_count", MIN_SPY_COUNT))
            spy_count = min(spy_count, int(len(player_list) * MAX_SPY_RATIO))  # 确保卧底不超过最大比例
            
            # 随机选择卧底
            roles_dict = {}  # 用户ID -> 角色
            
            # 随机打乱玩家列表
            random.shuffle(player_list)
            
            # 前spy_count个玩家为卧底
            spies = player_list[:spy_count]
            civilians = player_list[spy_count:]
            
            # 分配角色
            for player_id in spies:
                roles_dict[player_id] = ROLE_SPY
            
            for player_id in civilians:
                roles_dict[player_id] = ROLE_CIVILIAN
                
            # 如果有上帝，设置上帝角色
            if god_id:
                roles_dict[god_id] = ROLE_GOD
                
            # 4-6. 使用pipeline批量更新Redis数据
            try:
                # 获取pipeline对象
                pipe = await self.redis_client.pipeline()
                
                # 将角色信息保存到Redis
                role_key = ROOM_ROLES_KEY_PREFIX % room_id
                if roles_dict:
                    pipe.delete(role_key)
                    pipe.hmset(role_key, roles_dict)
                
                # 更新存活玩家列表
                alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
                # 先清空现有存活玩家
                pipe.delete(alive_players_key)
                # 添加所有玩家到存活列表（除了上帝）
                if player_list:
                    pipe.sadd(alive_players_key, *player_list)
                
                # 更新房间状态
                pipe.hset(room_key, "status", GAME_STATUS_PLAYING)
                pipe.hset(room_key, "current_round", "1")  # 设置当前回合为1
                pipe.hset(room_key, "current_phase", GAME_PHASE_SPEAKING)  # 设置当前阶段为发言阶段
                
                # 更新所有玩家状态
                for player_id in player_list:
                    pipe.hset(f"user:{player_id}", "status", USER_STATUS_PLAYING)
                
                # 执行所有命令
                await pipe.execute()
                
                logger.info(f"[{trace_id}] 游戏初始化Redis数据更新完成: 平民={len(civilians)}, 卧底={len(spies)}, 总玩家={len(player_list)}")
            
            except Exception as e:
                logger.error(f"[{trace_id}] Redis批量更新失败: {str(e)}", exc_info=True)
                raise
            
            logger.info(f"[{trace_id}] 游戏初始化完成: 房间={room_id}")
            
            # 给每个玩家发送私人角色和词语信息
            if self.websocket_manager:
                # 准备玩家列表信息（含AI标记）
                player_info_list = []
                
                # 并行获取所有玩家信息
                async def get_player_info(pid):
                    is_ai = pid.startswith("llm_player_")
                    player_data = await self.redis_client.get_user(pid)
                    return {
                        "id": pid,
                        "username": player_data.get("username", "未知玩家"),
                        "is_ai": is_ai,
                        "avatar_url": player_data.get("avatar_url", "/default_avatar.png")
                    }
                
                player_info_tasks = [get_player_info(pid) for pid in player_list]
                player_info_list = await asyncio.gather(*player_info_tasks)
                
                # 添加上帝到玩家列表信息（如果有）
                if god_id:
                    god_data = await self.redis_client.get_user(god_id)
                    god_info = {
                        "id": god_id,
                        "username": god_data.get("username", "未知玩家"),
                        "is_ai": False,  # 上帝不能是AI
                        "avatar_url": god_data.get("avatar_url", "/default_avatar.png"),
                        "is_god": True
                    }
                    player_info_list.append(god_info)
                
                # 准备广播任务列表
                broadcast_tasks = []
                
                # 给每个玩家发送角色信息和相应的词语
                for player_id, role in roles_dict.items():
                    word = civilian_word if role == ROLE_CIVILIAN else spy_word
                    
                    # 对于上帝角色，发送所有玩家的角色和两个词语
                    if role == ROLE_GOD:
                        broadcast_tasks.append(
                            self.websocket_manager.broadcast_message(
                                invite_code=room_id,
                                message={
                                    "type": "role_word_assignment",
                                    "role": role,
                                    "civilian_word": civilian_word, 
                                    "spy_word": spy_word,
                                    "is_god": True,
                                    "roles": roles_dict,  # 所有玩家的角色
                                    "players": player_info_list,  # 所有玩家信息（含AI标记）
                                    "timestamp": int(time.time() * 1000)
                                },
                                is_special=True,
                                target_users={player_id}
                            )
                        )
                    # 对于卧底角色，发送自己的角色、卧底词语和其他卧底队友
                    elif role == ROLE_SPY:
                        # 找出所有其他卧底玩家ID
                        spy_teammates = [pid for pid, r in roles_dict.items() 
                                        if r == ROLE_SPY and pid != player_id]
                        
                        broadcast_tasks.append(
                            self.websocket_manager.broadcast_message(
                                invite_code=room_id,
                                message={
                                    "type": "role_word_assignment",
                                    "role": role,
                                    "word": word,
                                    "spy_teammates": spy_teammates,  # 卧底队友ID列表
                                    "is_god": False,
                                    "players": player_info_list,  # 所有玩家信息（含AI标记）
                                    "timestamp": int(time.time() * 1000)
                                },
                                is_special=True,
                                target_users={player_id}
                            )
                        )
                    # 对于平民角色，只发送自己的角色和平民词语
                    else:
                        broadcast_tasks.append(
                            self.websocket_manager.broadcast_message(
                                invite_code=room_id,
                                message={
                                    "type": "role_word_assignment",
                                    "role": role,
                                    "word": word,
                                    "is_god": False,
                                    "players": player_info_list,  # 所有玩家信息（含AI标记）
                                    "timestamp": int(time.time() * 1000)
                                },
                                is_special=True,
                                target_users={player_id}
                            )
                        )
                
                # 并行执行所有广播任务
                if broadcast_tasks:
                    await asyncio.gather(*broadcast_tasks)
                    logger.info(f"[{trace_id}] 已并行完成所有广播任务")
                
            # 7. 返回成功结果
            result = {
                "success": True,
                "message": "游戏初始化成功",
                "data": {
                    "players": len(player_list),
                    "civilians": len(civilians),
                    "spies": len(spies),
                    "ai_players": ai_count
                }
            }
            
            return result
                
        except Exception as e:
            logger.error(f"初始化游戏失败: {str(e)}", exc_info=True)
            return {"success": False, "message": f"初始化游戏失败: {str(e)}"}


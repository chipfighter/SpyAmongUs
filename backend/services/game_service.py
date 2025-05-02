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
from typing import Dict, Any, List
import json

from utils.redis_utils import RedisClient
from config import (
    ROOM_KEY_PREFIX, ROOM_USERS_KEY_PREFIX,
    ROLE_SPY, ROLE_CIVILIAN, ROLE_GOD, GAME_STATUS_PLAYING, GAME_PHASE_SPEAKING,
    MIN_PLAYERS, ROOM_ROLES_KEY_PREFIX,
    ROOM_ALIVE_PLAYERS_KEY_PREFIX, USER_STATUS_PLAYING, GAME_STATUS_WAITING,
    VOTE_TIMEOUT, VOTE_SERVER_TIMEOUT, ROOM_VOTES_KEY_PREFIX
)

logger = logging.getLogger(__name__)

class GameService:
    def __init__(self, redis_client=None, websocket_manager=None):
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        self.message_service = None
        self.llm_pipeline = None  # 添加LLM转发层引用
        self.timeout_tasks = {}  # 用于跟踪超时任务
        if redis_client and websocket_manager:
            logger.info("GameService已初始化")
    
    def set_message_service(self, message_service):
        """设置消息服务，避免循环依赖"""
        self.message_service = message_service
        logger.info("GameService已连接到MessageService")
    
    def set_llm_pipeline(self, llm_pipeline):
        """设置LLM转发层，用于AI玩家发言"""
        self.llm_pipeline = llm_pipeline
        logger.info("GameService已连接到LLM Pipeline")
    
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
            
            # 更新房间的god_id字段
            room_key = f"{ROOM_KEY_PREFIX}{invite_code}"
            await self.redis_client.hset(room_key, "god_id", user_id)
            logger.info(f"[{response_trace_id}] 已将用户 {user_id} 设置为房间 {invite_code} 的上帝")

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
        2. 获取房间中所有真实玩家(含上帝)，并补充AI玩家到房间用户集合
        3. 对参与游戏的玩家(不含上帝)随机分配角色
        4. 记录角色信息到redis(含上帝角色)
        5. 更新存活玩家集合(只包含参与游戏的玩家，不含上帝)，更新房间状态为playing，更新普通用户状态为playing
        6. 向玩家发送角色和词语信息(根据角色类型发送不同信息):
           - 上帝: 知道所有玩家身份和两个词语
           - 平民: 只知道自己身份和平民词语
           - 卧底: 知道自己身份、卧底词语以及其他卧底队友
        7. 返回初始化成功的消息（让前端关闭初始化动画）
        
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
            
            # 使用异步io更新两个词语
            update_tasks = [
                self.redis_client.hset(room_key, "word_civilian", civilian_word),
                self.redis_client.hset(room_key, "word_spy", spy_word)
            ]
            await asyncio.gather(*update_tasks)
            
            logger.info(f"[{trace_id}] 词语已保存到房间 {room_id}")
            
            # 2. 获取房间中所有真实玩家(含上帝)
            real_players_with_god = await self.redis_client.get_room_users(room_id)
            if not real_players_with_god:
                logger.error(f"[{trace_id}] 房间 {room_id} 没有玩家，无法初始化游戏")
                return {"success": False, "message": "房间没有玩家"}
            
            # 获取上帝ID
            god_id = room_data.get("god_id", "")
            
            # 创建参与游戏的真实玩家列表(排除上帝)
            real_players = [p for p in real_players_with_god if p != god_id]
            logger.info(f"[{trace_id}] 真实玩家(含上帝): {real_players_with_god}, 参与游戏的真实玩家: {real_players}")
            
            # 计算需要补充的AI数量(考虑上帝占用位置)
            total_players = int(room_data.get("total_players", MIN_PLAYERS))
            ai_count = max(0, total_players - len(real_players_with_god))
            
            # 补充AI玩家到房间用户集合
            player_list = list(real_players)  # 游戏参与者(不含上帝)
            if ai_count > 0:
                for i in range(1, ai_count + 1):
                    ai_player_id = f"llm_player_{i}"
                    player_list.append(ai_player_id)
                    
                    # 将AI玩家添加到房间用户集合(room:users，包含所有用户)
                    room_users_keys = ROOM_USERS_KEY_PREFIX % room_id
                    await self.redis_client.zadd(room_users_keys, {ai_player_id: int(time.time() * 1000)})
                
                logger.info(f"[{trace_id}] 补充了 {ai_count} 个AI玩家到房间 {room_id}")
            
            # 3. 随机分配角色(对不含上帝的玩家列表进行分配)

            # 直接读取需要的卧底数量
            spy_count = int(await self.redis_client.hget(room_key, "spy_count"))
            
            # 随机选择卧底
            roles_dict = {}  # 用户ID -> 角色
            
            # 随机打乱玩家列表
            random.shuffle(player_list)
            
            # 直接切片快速处理，前spy_count个玩家为卧底
            spies = player_list[:spy_count]
            civilians = player_list[spy_count:]
            
            # 4. 设置角色(包括上帝)
            for player_id in spies:
                roles_dict[player_id] = ROLE_SPY
            
            for player_id in civilians:
                roles_dict[player_id] = ROLE_CIVILIAN
                
            if god_id:
                roles_dict[god_id] = ROLE_GOD
                
            # 在角色分配后，再次打乱玩家列表，确保发言顺序与角色分配无关
            random.shuffle(player_list)
            logger.info(f"[{trace_id}] 角色分配后再次打乱玩家列表，新顺序: {player_list}")
                
            # 5. 使用pipeline批量更新Redis数据
            try:
                # 获取pipeline对象
                pipe = await self.redis_client.pipeline()
                
                # 将角色信息保存到Redis(包含所有玩家和上帝)
                role_key = ROOM_ROLES_KEY_PREFIX % room_id
                if roles_dict:
                    pipe.delete(role_key)
                    pipe.hmset(role_key, roles_dict)
                
                # 更新存活玩家列表(不含上帝，只有参与游戏的玩家)
                # 使用二次打乱后的player_list创建alive_members
                alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
                logger.info(f"[DEBUG] initialize_game: 开始初始化存活玩家集合 {alive_players_key}")
                
                # 检查玩家列表是否为空
                if not player_list:
                    logger.error(f"[DEBUG] initialize_game: 玩家列表为空，无法初始化存活玩家")
                
                alive_members = {player_id: idx for idx, player_id in enumerate(player_list)}
                logger.info(f"[DEBUG] initialize_game: 将添加到存活玩家集合的玩家及分数: {alive_members}")
                
                pipe.delete(alive_players_key)
                pipe.zadd(alive_players_key, alive_members)
                logger.info(f"[DEBUG] initialize_game: 添加alive_members命令已加入管道")
                
                # 更新房间状态
                pipe.hset(room_key, "status", GAME_STATUS_PLAYING)
                pipe.hset(room_key, "current_round", "1")  # 设置当前回合为1
                pipe.hset(room_key, "current_phase", GAME_PHASE_SPEAKING)  # 设置当前阶段为发言阶段
                
                # 只更新真实玩家的状态(不包括AI和上帝)
                for player_id in real_players:
                    if not player_id.startswith("llm_player_"):
                        pipe.hset(f"user:{player_id}", "status", USER_STATUS_PLAYING)
                
                # 执行所有命令
                logger.info(f"[DEBUG] initialize_game: 开始执行Redis管道命令")
                pipe_result = await pipe.execute()
                logger.info(f"[DEBUG] initialize_game: Redis管道执行结果: {pipe_result}")
                
                # 执行后验证存活玩家列表
                try:
                    alive_verification = await self.redis_client.zrange(alive_players_key, 0, -1, withscores=True)
                    logger.info(f"[DEBUG] initialize_game: 验证后的存活玩家列表: {alive_verification}")
                except Exception as e:
                    logger.error(f"[DEBUG] initialize_game: 验证存活玩家列表失败: {str(e)}", exc_info=True)
                
                logger.info(f"[{trace_id}] 游戏初始化Redis数据更新完成: 平民={len(civilians)}, 卧底={len(spies)}, 总玩家={len(player_list)}")
            
            except Exception as e:
                logger.error(f"[{trace_id}] Redis批量更新失败: {str(e)}", exc_info=True)
                raise
            
            logger.info(f"[{trace_id}] 游戏初始化完成: 房间={room_id}")
            
            # 6. 给每个玩家发送私人角色和词语信息
            if self.websocket_manager:
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
                                    "player_ids": player_list,  # 所有玩家ID列表
                                    "current_phase": GAME_PHASE_SPEAKING,
                                    "current_round": 1,
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
                                    "spy_word": word,
                                    "spy_teammates": spy_teammates,  # 卧底队友ID列表
                                    "is_god": False,
                                    "god_id": god_id,
                                    "player_ids": player_list,  # 所有玩家ID列表
                                    "current_phase": GAME_PHASE_SPEAKING,
                                    "current_round": 1,
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
                                    "civilian_word": word,
                                    "is_god": False,
                                    "god_id": god_id,
                                    "player_ids": player_list,  # 所有玩家ID列表
                                    "current_phase": GAME_PHASE_SPEAKING,
                                    "current_round": 1,
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
            
            # 启动发言阶段
            asyncio.create_task(self.start_speaking_phase(room_id))
            
            return result
                
        except Exception as e:
            logger.error(f"初始化游戏失败: {str(e)}", exc_info=True)
            return {"success": False, "message": f"初始化游戏失败: {str(e)}"}

    async def start_speaking_phase(self, room_id: str) -> None:
        """
        游戏初始化完成后启动发言阶段
        
        Args:
            room_id: 房间ID

        Notes:
            发言阶段的设置以及回合初始化放置于初始化函数中
        """
        try:
            logger.info(f"开始房间 {room_id} 的发言阶段")
            
            # 创建轮次发言记录集合，用于跟踪已发言玩家
            round_speakers_key = f"room:{room_id}:round_speakers"
            await self.redis_client.delete(round_speakers_key)
            
            # 广播游戏阶段变更消息
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message={
                    "type": "game_phase_update",
                    "phase": GAME_PHASE_SPEAKING,
                    "message": "发言阶段开始"
                },
                is_special=False
            )
            
            # 开始第一个玩家的发言
            await self.announce_next_speaker(room_id)
            
        except Exception as e:
            logger.error(f"启动发言阶段失败: {str(e)}")

    async def announce_next_speaker(self, room_id: str) -> None:
        """
        宣布并广播下一个发言者
        
        Args:
            room_id: 房间ID
        """
        try:
            # 获取当前发言者
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            logger.info(f"[DEBUG] 尝试从 {alive_players_key} 获取存活玩家列表")
            
            # 先检查键是否存在
            key_exists = await self.redis_client.exists(alive_players_key)
            logger.info(f"[DEBUG] 键 {alive_players_key} 是否存在: {key_exists}")
            
            # 获取所有存活玩家，用于调试
            all_alive_players = await self.redis_client.zrange(alive_players_key, 0, -1, withscores=True)
            logger.info(f"[DEBUG] 所有存活玩家及分数: {all_alive_players}")
            
            # 获取当前发言者（第一个玩家）
            try:
                current_speakers = await self.redis_client.zrange(alive_players_key, 0, 0)
                logger.info(f"[DEBUG] zrange(0,0)返回的当前发言者: {current_speakers}, 类型: {type(current_speakers)}")
            except Exception as e:
                logger.error(f"[DEBUG] 获取当前发言者时发生异常: {str(e)}", exc_info=True)
                current_speakers = []
            
            if not current_speakers:
                logger.error(f"房间 {room_id} 没有存活玩家，无法确定下一个发言者")
                # 尝试直接从Redis获取，用于诊断
                try:
                    raw_response = await self.redis_client._redis.zrange(alive_players_key, 0, 0)
                    logger.info(f"[DEBUG] 直接使用_redis.zrange获取的结果: {raw_response}")
                except Exception as e:
                    logger.error(f"[DEBUG] 直接调用底层Redis时发生异常: {str(e)}", exc_info=True)
                return
            
            current_speaker = current_speakers[0]
            logger.info(f"[DEBUG] 当前发言者确定为: {current_speaker}")
            
            # 获取发言时间限制
            room_data = await self.redis_client.get_room_basic_data(room_id)
            speak_time = int(room_data.get("speak_time", 60))
            
            # 获取当前发言者信息
            if current_speaker.startswith("llm_player_"):
                # AI玩家
                speaker_name = f"AI玩家_{current_speaker.replace('llm_player_', '')}"
            else:
                # 真实玩家
                speaker_info = await self.redis_client.hgetall(f"user:{current_speaker}")
                speaker_name = speaker_info.get("username", "未知玩家")
            
            logger.info(f"房间 {room_id} 当前发言者: {speaker_name} ({current_speaker})")
            
            # 向全部用户广播发言轮次消息
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message={
                    "type": "speaking_turn",
                    "speaker_id": current_speaker,
                    "speaker_name": speaker_name,
                    "time_limit": speak_time,
                    "word_limit": 70,
                    "message": f"轮到 {speaker_name} 发言"
                },
                is_special=False
            )
            
            # 如果是AI玩家，自动处理AI发言
            if current_speaker.startswith("llm_player_"):
                # 调用AI玩家发言处理
                logger.info(f"检测到AI玩家 {current_speaker}，开始生成AI发言")
                asyncio.create_task(self.handle_ai_player_speaking(room_id, current_speaker))
            
        except Exception as e:
            logger.error(f"宣布下一个发言者失败: {str(e)}", exc_info=True)

    async def handle_ai_player_speaking(self, room_id: str, ai_player_id: str) -> None:
        """
        处理AI玩家发言
        
        Args:
            room_id: 房间ID
            ai_player_id: AI玩家ID
        """
        try:
            # 1. 获取游戏基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = room_data.get("current_round", "1")
            max_rounds = room_data.get("max_rounds", "5")
            
            # 获取发言时间限制（秒）
            speak_time_limit = int(room_data.get("speak_time", 60))
            # 添加额外缓冲时间（3秒）
            ai_timeout = speak_time_limit + 3
            
            # 2. 获取AI玩家角色和词语
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            player_role = await self.redis_client.hget(role_key, ai_player_id)
            
            # 获取词语信息
            civilian_word = await self.redis_client.hget(room_key, "word_civilian")
            spy_word = await self.redis_client.hget(room_key, "word_spy")
            word = spy_word if player_role == ROLE_SPY else civilian_word
            
            # 3. 获取玩家信息
            # 3.1 获取所有玩家和存活玩家
            all_players = await self.redis_client.get_room_users(room_id)
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            alive_players = await self.redis_client.zrange(alive_players_key, 0, -1)
            
            # 3.2 统计卧底信息（仅当前玩家是卧底时需要）
            spy_teammates = []
            spy_count = int(room_data.get("spy_count", "1"))
            remaining_spy_count = 0
            
            if player_role == ROLE_SPY:
                # 当前玩家是卧底，获取所有卧底信息
                for player_id in all_players:
                    role = await self.redis_client.hget(role_key, player_id)
                    if role == ROLE_SPY:
                        # 检查该卧底是否仍然存活
                        if player_id in alive_players:
                            remaining_spy_count += 1
                        
                        # 如果不是当前AI玩家自己，添加到队友列表
                        if player_id != ai_player_id:
                            # 获取卧底玩家名称
                            if player_id.startswith("llm_player_"):
                                teammate_name = f"AI玩家_{player_id.replace('llm_player_', '')}"
                            else:
                                player_data = await self.redis_client.hgetall(f"user:{player_id}")
                                teammate_name = player_data.get("username", "未知玩家")
                            
                            spy_teammates.append(f"{player_id} ({teammate_name})")
                
            # 处理卧底队友信息
            spy_teammates_str = "无" if not spy_teammates else ", ".join(spy_teammates)
            
            # 4. 构建游戏信息字典
            game_info = {
                "role": "spy" if player_role == ROLE_SPY else "civilian",
                "word": word,
                "current_round": current_round,
                "max_rounds": max_rounds,
                "player_count": len(all_players),
                "alive_count": len(alive_players),
                "eliminated_players": ", ".join([p for p in all_players if p not in alive_players]) or "无",
                "total_spy_count": spy_count,
                "remaining_spy_count": remaining_spy_count,
                "spy_teammates": spy_teammates_str,
                "ai_player_id": ai_player_id,  # 添加AI玩家ID，让LLM知道自己是谁
                "speak_time": int(room_data.get("speak_time", 60))  # 添加发言时间限制
            }
            
            # 获取AI玩家显示名称
            ai_username = f"AI玩家_{ai_player_id.replace('llm_player_', '')}"
            
            # 5. 生成时间戳作为唯一标识
            timestamp = int(time.time() * 1000)
            session_id = f"ai_session_{room_id}_{timestamp}"
            logger.info(f"创建AI玩家 {ai_player_id} 发言会话: {session_id}")
            
            # 6. 获取聊天历史 - 使用Redis Utils的方法
            # 获取聊天历史并转换为Message对象列表
            messages_history = await self.redis_client.get_room_messages(room_id, 15)
            
            # 如果返回的是Message对象，需要转换为列表
            from models.message import Message
            if messages_history and isinstance(messages_history[0], Message):
                messages = messages_history
            else:
                # 可能返回的是字典列表，转换为Message对象
                messages = []
                for msg_dict in messages_history:
                    try:
                        message = Message(
                            timestamp=msg_dict.get("timestamp", int(time.time() * 1000)),
                            user_id=msg_dict.get("user_id", ""),
                            username=msg_dict.get("username", "Unknown"),
                            content=msg_dict.get("content", ""),
                            is_system=msg_dict.get("type") == "system"
                        )
                        messages.append(message)
                    except Exception as e:
                        logger.error(f"转换消息对象失败: {str(e)}")
                        continue
            
            # 7. 广播AI准备状态消息（前端会显示气泡和加载动画）
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message={
                    "type": "ai_stream",
                    "user_id": ai_player_id,
                    "username": ai_username,
                    "is_start": True,
                    "is_end": False,
                    "content": "",  # 内容为空，前端会显示加载动画
                    "timestamp": timestamp,
                    "session_id": session_id
                },
                is_special=False
            )
            logger.info(f"已广播AI玩家 {ai_player_id} 准备状态，前端将显示加载动画")
            
            # 添加短暂延迟，模拟AI思考时间 (2-4秒的随机延迟)
            import random
            thinking_delay = random.uniform(2.0, 4.0)
            logger.info(f"AI玩家 {ai_player_id} 正在思考，延迟 {thinking_delay:.2f} 秒")
            await asyncio.sleep(thinking_delay)
            
            # 8. 初始化流式响应参数
            full_ai_response = ""  # 存储完整响应
            is_first_chunk = True
            last_chunk_end = ""  # 跟踪上一块结尾
            
            # 9. 创建超时保护任务
            got_response = False
            
            # 超时处理函数
            async def handle_timeout():
                nonlocal got_response
                try:
                    await asyncio.sleep(ai_timeout)
                    if not got_response:
                        logger.warning(f"AI玩家 {ai_player_id} 发言超时")
                        
                        # 发送超时消息
                        timeout_message = "我还没想好..."
                        
                        # 广播超时消息给所有用户
                        await self.websocket_manager.broadcast_message(
                            invite_code=room_id,
                            message={
                                "type": "chat",
                                "user_id": ai_player_id,
                                "username": ai_username,
                                "content": timeout_message,
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        
                        # 创建符合Message模型的消息对象，包含round信息
                        ai_message = Message(
                            user_id=ai_player_id,
                            username=ai_username,
                            content=timeout_message,
                            timestamp=int(time.time() * 1000),
                            is_system=False,
                            round=current_round  # 添加当前回合信息
                        )
                        
                        # 将消息对象转换为字典并存储到Redis
                        await self.redis_client.lpush(
                            f"room:{room_id}:messages", 
                            json.dumps(ai_message.dict())
                        )
                        
                        # 设置过期时间(24小时)
                        await self.redis_client.expire(
                            f"room:{room_id}:messages", 
                            24 * 60 * 60
                        )
                        
                        # 继续下一个发言者
                        await self.move_to_next_speaker(room_id)
                except Exception as e:
                    logger.error(f"处理AI发言超时时出错: {str(e)}")
            
            # 启动超时保护任务
            timeout_task = asyncio.create_task(handle_timeout())
            
            try:
                # 当LLM Pipeline可用时，调用它生成响应
                if self.llm_pipeline:
                    # 由于是游戏中的发言，所有发言提示应该与角色身份相关
                    async for chunk in self.llm_pipeline.chat_completion(
                        messages=messages,  # 直接传递Message对象列表
                        current_message=f"作为AI玩家 {ai_player_id}，请根据你的角色和词语({word})，给出一段描述：",
                        context_type="game_playing",
                        game_info=game_info
                    ):
                        # 标记已获得响应
                        got_response = True
                        
                        # 累积完整响应
                        full_ai_response += chunk
                        
                        # 处理跨块边界的连续换行问题
                        import re
                        check_str = last_chunk_end + chunk
                        processed_chunk = re.sub(r'\n{3,}', '\n\n', check_str)
                        
                        # 只发送不包含上一个块末尾的内容
                        if last_chunk_end and len(processed_chunk) > len(last_chunk_end):
                            processed_chunk = processed_chunk[len(last_chunk_end):]
                        elif last_chunk_end:
                            # 如果处理后的内容小于或等于上一块结尾，说明全是重复内容
                            processed_chunk = ""
                        
                        # 更新末尾追踪
                        last_chunk_end = chunk[-3:] if len(chunk) >= 3 else chunk
                        
                        # 构造流式消息
                        chunk_timestamp = int(time.time() * 1000)
                        stream_message = {
                            "timestamp": chunk_timestamp,
                            "type": "ai_stream",
                            "user_id": ai_player_id,
                            "username": ai_username,
                            "is_start": False,
                            "is_end": False,
                            "content": processed_chunk,
                            "session_id": session_id
                        }
                        
                        # 广播到房间
                        await self.websocket_manager.broadcast_message(
                            invite_code=room_id, 
                            message=stream_message,
                            is_special=False
                        )
                        
                        # 添加短暂延迟，模拟打字效果
                        # 根据块长度决定延迟时间，每个字符大约需要0.05秒
                        char_count = len(processed_chunk)
                        typing_delay = min(0.5, max(0.1, char_count * 0.05))  # 最少0.1秒，最多0.5秒
                        await asyncio.sleep(typing_delay)
                        
                        # 让出控制权
                        await asyncio.sleep(0)
                        
                        # 更新第一个块标志
                        if is_first_chunk:
                            is_first_chunk = False
                    
                    # 10. 发送结束标记
                    end_timestamp = int(time.time() * 1000)
                    end_message = {
                        "timestamp": end_timestamp,
                        "type": "ai_stream",
                        "user_id": ai_player_id,
                        "username": ai_username,
                        "is_start": False,
                        "is_end": True,
                        "content": "",
                        "session_id": session_id
                    }
                    
                    await self.websocket_manager.broadcast_message(
                        invite_code=room_id, 
                        message=end_message, 
                        is_special=False
                    )
                    
                    # 11. 存储完整消息到Redis
                    # 处理AI响应（去除多余的空行）
                    processed_ai_response = re.sub(r'\n{3,}', '\n\n', full_ai_response)
                    
                    # 创建符合Message模型的消息对象，包含round信息
                    ai_message = Message(
                        user_id=ai_player_id,
                        username=ai_username,
                        content=processed_ai_response,
                        timestamp=int(time.time() * 1000),
                        is_system=False,
                        round=current_round  # 添加当前回合信息
                    )
                    
                    # 将消息对象转换为字典并存储到Redis
                    await self.redis_client.lpush(
                        f"room:{room_id}:messages", 
                        json.dumps(ai_message.dict())
                    )
                    
                    # 设置过期时间(24小时)
                    await self.redis_client.expire(
                        f"room:{room_id}:messages", 
                        24 * 60 * 60
                    )
                    
                    logger.info(f"AI玩家 {ai_player_id} 发言完成，已存储消息")
                else:
                    # LLM Pipeline不可用，发送默认消息
                    logger.error(f"LLM Pipeline不可用，AI玩家 {ai_player_id} 将使用默认消息")
                    default_message = "这个词语我知道，但不太好描述..."
                    
                    # 标记已获得响应
                    got_response = True
                    
                    # 广播默认消息
                    await self.websocket_manager.broadcast_message(
                        invite_code=room_id,
                        message={
                            "type": "chat",
                            "user_id": ai_player_id,
                            "username": ai_username,
                            "content": default_message,
                            "timestamp": int(time.time() * 1000)
                        },
                        is_special=False
                    )
                    
                    # 创建符合Message模型的消息对象，包含round信息
                    ai_message = Message(
                        user_id=ai_player_id,
                        username=ai_username,
                        content=default_message,
                        timestamp=int(time.time() * 1000),
                        is_system=False,
                        round=current_round  # 添加当前回合信息
                    )
                    
                    # 将消息对象转换为字典并存储到Redis
                    await self.redis_client.lpush(
                        f"room:{room_id}:messages", 
                        json.dumps(ai_message.dict())
                    )
                    
                    # 设置过期时间(24小时)
                    await self.redis_client.expire(
                        f"room:{room_id}:messages", 
                        24 * 60 * 60
                    )
                
                # 如果收到了响应，取消超时任务
                if got_response:
                    timeout_task.cancel()
                    # 短暂延迟后继续游戏流程
                    await asyncio.sleep(1)
                    await self.move_to_next_speaker(room_id)
            
            except asyncio.CancelledError:
                # 处理超时任务被取消的情况
                logger.info(f"AI玩家 {ai_player_id} 发言任务被取消")
            except Exception as e:
                logger.error(f"AI玩家 {ai_player_id} 发言处理过程中出错: {str(e)}")
                # 确保继续游戏流程
                if not got_response:
                    # 模拟超时处理
                    got_response = True
                    timeout_task.cancel()
                    await handle_timeout()
                
            finally:
                # 确保超时任务被清理
                if not timeout_task.done():
                    timeout_task.cancel()
                    
        except Exception as e:
            logger.error(f"处理AI玩家发言失败: {str(e)}")
            # 发生错误时，仍然继续下一个发言者
            await self.move_to_next_speaker(room_id)
    
    async def move_to_next_speaker(self, room_id: str) -> None:
        """
        移动到下一个发言者
        
        Args:
            room_id: 房间ID
        """
        try:
            # 获取当前发言者
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            logger.info(f"[DEBUG] move_to_next_speaker: 尝试从 {alive_players_key} 获取当前发言者")
            
            try:
                current_speaker = await self.redis_client.zrange(alive_players_key, 0, 0)
                logger.info(f"[DEBUG] move_to_next_speaker: 获取到的当前发言者: {current_speaker}")
            except Exception as e:
                logger.error(f"[DEBUG] move_to_next_speaker: 获取当前发言者时发生异常: {str(e)}", exc_info=True)
                current_speaker = []
            
            if not current_speaker:
                logger.error(f"房间 {room_id} 没有存活玩家，无法移动到下一个发言者")
                
                # 尝试恢复游戏状态
                try:
                    room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                    current_phase = await self.redis_client.hget(room_key, "current_phase")
                    logger.warning(f"错误恢复：房间 {room_id} 没有存活玩家，当前阶段是 {current_phase}，尝试进入投票阶段")
                    
                    # 强制进入投票阶段
                    await self.redis_client.hset(room_key, "current_phase", "speaking")
                    await self.start_voting_phase(room_id)
                except Exception as recovery_error:
                    logger.error(f"错误恢复失败: {str(recovery_error)}", exc_info=True)
                return
            
            current_speaker = current_speaker[0]
            logger.info(f"[DEBUG] move_to_next_speaker: 当前发言者确定为: {current_speaker}")
            
            # 将当前发言者移到队列末尾
            # 使用当前时间戳作为分数，确保顺序
            new_score = time.time() * 1000
            logger.info(f"[DEBUG] move_to_next_speaker: 将玩家 {current_speaker} 移到队列末尾，新分数: {new_score}")
            await self.redis_client.zadd(alive_players_key, {current_speaker: new_score})
            
            # 标记该玩家已发言
            round_speakers_key = f"room:{room_id}:round_speakers"
            await self.redis_client.sadd(round_speakers_key, current_speaker)
            
            # 检查是否所有玩家都已发言
            all_players = await self.redis_client.zrange(alive_players_key, 0, -1, withscores=False)
            logger.info(f"[DEBUG] move_to_next_speaker: 所有存活玩家: {all_players}")
            
            spoke_players = await self.redis_client.smembers(round_speakers_key)
            logger.info(f"[DEBUG] move_to_next_speaker: 已发言玩家: {spoke_players}")
            
            if set(spoke_players) == set(all_players):
                # 所有玩家都已发言，进入下一个阶段
                logger.info(f"房间 {room_id} 所有玩家都已发言，准备进入投票阶段")
                
                # 清理发言记录
                await self.redis_client.delete(round_speakers_key)

                # 获取当前房间阶段
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                current_phase = await self.redis_client.hget(room_key, "current_phase")
                
                # 确保当前阶段为speaking，无论之前的值是什么
                await self.redis_client.hset(room_key, "current_phase", "speaking")
                logger.info(f"房间 {room_id} 当前阶段是 {current_phase}，强制设置为speaking后准备进入投票阶段")
                
                # 开始投票阶段
                await self.start_voting_phase(room_id)
            else:
                # 还有玩家未发言，继续下一个
                logger.info(f"房间 {room_id} 继续下一个玩家发言")
                await self.announce_next_speaker(room_id)
            
        except Exception as e:
            logger.error(f"移动到下一个发言者失败: {str(e)}", exc_info=True)
            # 尝试恢复游戏流程
            try:
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                current_phase = await self.redis_client.hget(room_key, "current_phase")
                logger.warning(f"错误恢复：房间 {room_id} 当前阶段是 {current_phase}，尝试继续游戏流程")
                
                if current_phase == "speaking":
                    # 如果仍在发言阶段，尝试通知下一个发言者
                    await self.announce_next_speaker(room_id)
                else:
                    # 如果不是发言阶段，强制设置为发言阶段并进入投票阶段
                    logger.warning(f"错误恢复：房间 {room_id} 当前阶段是 {current_phase}，尝试强制进入投票阶段")
                    await self.redis_client.hset(room_key, "current_phase", "speaking")
                    await self.start_voting_phase(room_id)
            except Exception as recovery_error:
                logger.error(f"错误恢复失败: {str(recovery_error)}", exc_info=True)

    async def start_voting_phase(self, room_id: str) -> None:
        """
        开始投票阶段
        
        Args:
            room_id: 房间ID
        """
        try:
            # 1. 获取存活玩家列表
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            alive_players = await self.redis_client.zrange(alive_players_key, 0, -1)
            
            # 2. 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = room_data.get("current_round", "1")
            
            # 3. 构建投票开始消息
            vote_start_message = {
                "type": "vote_phase_start",
                "current_phase": "voting",
                "current_round": current_round,
                "alive_players": alive_players,
                "vote_timeout": VOTE_TIMEOUT,
                "timestamp": int(time.time() * 1000)
            }
            
            # 4. 广播投票开始消息
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=vote_start_message,
                is_special=False
            )
            
            # 5. 更新房间状态为投票阶段
            await self.redis_client.hset(room_key, "current_phase", "voting")
            
            # 6. 设置投票超时任务
            vote_timeout_task = asyncio.create_task(self._handle_vote_timeout(room_id, VOTE_SERVER_TIMEOUT))
            
            # 7. 为AI玩家安排投票
            for player_id in alive_players:
                if player_id.startswith("llm_player_"):
                    # 为每个AI玩家创建异步任务，模拟思考时间后投票
                    delay_time = random.uniform(3.0, 8.0)  # 随机3-8秒延迟
                    asyncio.create_task(self._handle_ai_player_vote(room_id, player_id, delay_time))
            
            logger.info(f"房间 {room_id} 投票阶段开始")
            
        except Exception as e:
            logger.error(f"开始投票阶段失败: {str(e)}")

    async def _handle_ai_player_vote(self, room_id: str, ai_player_id: str, delay_seconds: float) -> None:
        """
        处理AI玩家投票
        
        Args:
            room_id: 房间ID
            ai_player_id: AI玩家ID
            delay_seconds: 延迟秒数
        """
        try:
            # 1. 延迟一段时间，模拟思考
            await asyncio.sleep(delay_seconds)
            
            # 2. 获取当前房间阶段
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            current_phase = await self.redis_client.hget(room_key, "current_phase")
            
            # 如果不是投票阶段了，直接返回
            if current_phase != "voting":
                logger.info(f"AI玩家 {ai_player_id} 投票取消: 当前阶段已不是投票阶段")
                return
                
            # 3. 获取存活玩家列表，排除自己
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            
            # 确认AI玩家是存活的
            ai_player_exists = await self.redis_client.zrank(alive_players_key, ai_player_id)
            if ai_player_exists is None:
                logger.warning(f"AI玩家 {ai_player_id} 已不在存活玩家列表中，取消投票")
                return
                
            # 获取所有存活玩家
            alive_players = await self.redis_client.zrange(alive_players_key, 0, -1)
            other_players = [p for p in alive_players if p != ai_player_id]
            
            if not other_players:
                logger.warning(f"AI玩家 {ai_player_id} 没有可投票的目标")
                return
            
            # 4. 获取当前轮次和投票状态
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = room_data.get("current_round", "1")
            vote_key = f"room:{room_id}:votes:{current_round}"
            
            # 检查AI是否已经投票
            if await self.redis_client.hexists(vote_key, ai_player_id):
                logger.info(f"AI玩家 {ai_player_id} 已经投过票了")
                return
            
            # 5. 获取玩家角色信息
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            roles = await self.redis_client.hgetall(role_key)
            ai_role = roles.get(ai_player_id)
            
            if not ai_role:
                logger.error(f"AI玩家 {ai_player_id} 没有角色信息，无法进行投票")
                return
                
            target_id = None
            
            # 6. 根据角色决定投票策略
            if ai_role == ROLE_SPY:  # 卧底尽量不投卧底
                # 找出所有非卧底玩家
                non_spy_players = [p for p in other_players if roles.get(p) != ROLE_SPY]
                if non_spy_players:
                    target_id = random.choice(non_spy_players)
                    logger.info(f"AI卧底 {ai_player_id} 选择投票给非卧底玩家 {target_id}")
                else:
                    target_id = random.choice(other_players)  # 如果都是卧底，随机选一个
                    logger.info(f"AI卧底 {ai_player_id} 没有找到非卧底玩家，随机投票给 {target_id}")
            else:  # 平民随机投
                target_id = random.choice(other_players)
                logger.info(f"AI平民 {ai_player_id} 随机投票给 {target_id}")
            
            if target_id:
                # 7. 执行投票
                logger.info(f"AI玩家 {ai_player_id} 决定投票给 {target_id}")
                vote_result = await self.handle_player_vote(room_id, ai_player_id, target_id)
                
                if vote_result["success"]:
                    logger.info(f"AI玩家 {ai_player_id} 投票成功")
                else:
                    logger.warning(f"AI玩家 {ai_player_id} 投票失败: {vote_result['message']}")
            else:
                logger.error(f"AI玩家 {ai_player_id} 未能确定投票目标")
            
        except Exception as e:
            logger.error(f"AI玩家 {ai_player_id} 投票失败: {str(e)}", exc_info=True)

    async def _handle_vote_timeout(self, room_id: str, timeout_seconds: float) -> None:
        """
        处理投票超时
        
        Args:
            room_id: 房间ID
            timeout_seconds: 超时时间（秒）
        """
        try:
            # 等待指定的超时时间
            await asyncio.sleep(timeout_seconds)
            
            logger.info(f"房间 {room_id} 投票时间已到，开始统计结果")
            
            # 获取当前房间阶段，确认还在投票阶段
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            current_phase = await self.redis_client.hget(room_key, "current_phase")
            
            # 如果不是投票阶段了，可能是其他函数已经处理了结果
            if current_phase != "voting":
                logger.info(f"房间 {room_id} 已不在投票阶段 (当前阶段: {current_phase})，跳过统计")
                return
            
            # 统计投票结果
            result = await self.tally_votes(room_id)
            
            if result["success"]:
                # 处理投票结果
                eliminated_player_id = result.get("eliminated_player_id")
                if eliminated_player_id:
                    logger.info(f"玩家 {eliminated_player_id} 被投票淘汰")
                    
                    # 淘汰玩家 (会处理遗言阶段)
                    await self.eliminate_player(room_id, eliminated_player_id)
                else:
                    logger.warning(f"房间 {room_id} 没有投票或投票平局，无法确定被淘汰玩家")
                    
                    # 发送平局或无人投票消息
                    reason = result.get("reason", "tie")
                    message_text = "投票结束，没有玩家被淘汰" if reason == "tie" else "投票时间结束，无人投票，游戏继续"
                    
                    vote_result_message = {
                        "type": "vote_result",
                        "result": reason,
                        "message": message_text,
                        "timestamp": int(time.time() * 1000)
                    }
                    
                    await self.websocket_manager.broadcast_message(
                        invite_code=room_id,
                        message=vote_result_message,
                        is_special=False
                    )
                    
                    # 发送系统消息
                    system_message = {
                        "type": "system",
                        "content": message_text,
                        "timestamp": int(time.time() * 1000)
                    }
                    
                    await self.websocket_manager.broadcast_message(
                        invite_code=room_id,
                        message=system_message,
                        is_special=False
                    )
                    
                    # 检查游戏是否结束
                    game_end_result = await self.check_game_end_condition(room_id)
                    
                    if game_end_result["game_end"]:
                        # 游戏结束，广播游戏结果
                        await self.broadcast_game_result(room_id, game_end_result)
                    else:
                        # 游戏未结束，开始下一轮
                        logger.info(f"投票无结果，房间 {room_id} 准备进入下一轮")
                        asyncio.create_task(self._safe_start_next_round(room_id))
            else:
                logger.error(f"统计投票结果失败: {result.get('message', '未知错误')}")
                
                # 尝试错误恢复
                try:
                    # 检查游戏是否应该结束
                    game_end_result = await self.check_game_end_condition(room_id)
                    
                    if game_end_result["game_end"]:
                        # 游戏结束，广播游戏结果
                        logger.warning(f"投票统计失败，但游戏结束条件已满足，广播结果")
                        await self.broadcast_game_result(room_id, game_end_result)
                    else:
                        # 游戏未结束，强制开始下一轮
                        logger.warning(f"投票统计失败，尝试强制开始新回合")
                        await self.redis_client.hset(room_key, "current_phase", "voting_ended")
                        asyncio.create_task(self._safe_start_next_round(room_id))
                except Exception as recovery_error:
                    logger.error(f"投票错误恢复失败: {str(recovery_error)}", exc_info=True)
        
        except asyncio.CancelledError:
            logger.info(f"房间 {room_id} 投票超时任务被取消")
        except Exception as e:
            logger.error(f"处理投票超时出错: {str(e)}", exc_info=True)
            
            # 出错时尝试恢复游戏流程
            try:
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                current_phase = await self.redis_client.hget(room_key, "current_phase")
                
                if current_phase == "voting":
                    # 如果仍在投票阶段，尝试强制进入下一轮
                    logger.warning(f"投票处理出错，尝试强制开始新回合")
                    await self.redis_client.hset(room_key, "current_phase", "voting_error")
                    asyncio.create_task(self._safe_start_next_round(room_id))
            except Exception as recovery_error:
                logger.error(f"投票错误恢复失败: {str(recovery_error)}", exc_info=True)

    async def check_game_end_condition(self, room_id: str) -> Dict[str, Any]:
        """
        检查游戏是否结束
        
        Args:
            room_id: 房间ID
            
        Returns:
            Dict: {
                game_end: bool,  # 游戏是否结束
                winning_role: str,  # 获胜角色 civilian/spy
                reason: str  # 结束原因
            }
        """
        try:
            logger.info(f"检查房间 {room_id} 游戏结束条件")
            
            # 获取所有角色信息
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            all_roles = await self.redis_client.hgetall(role_key)
            
            if not all_roles:
                logger.warning(f"房间 {room_id} 没有角色信息，可能游戏未开始或数据已被清理")
                return {
                    "game_end": False,
                    "winning_role": "",
                    "reason": "没有角色信息"
                }
            
            # 获取存活玩家
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            alive_players = await self.redis_client.zrange(alive_players_key, 0, -1, withscores=False)
            
            if not alive_players:
                logger.warning(f"房间 {room_id} 没有存活玩家，可能游戏未开始或数据异常")
                return {
                    "game_end": False,
                    "winning_role": "",
                    "reason": "没有存活玩家"
                }
            
            # 计算存活玩家数量
            civilian_count = 0
            spy_count = 0
            
            # 详细记录每个玩家的角色
            player_roles_log = []
            
            for player_id in alive_players:
                role = all_roles.get(player_id)
                player_roles_log.append(f"{player_id}:{role}")
                
                if role == ROLE_CIVILIAN:
                    civilian_count += 1
                elif role == ROLE_SPY:
                    spy_count += 1
            
            logger.info(f"房间 {room_id} 存活玩家角色统计: 总数={len(alive_players)}, 平民={civilian_count}, 卧底={spy_count}")
            logger.debug(f"详细存活玩家角色: {', '.join(player_roles_log)}")
            
            # 判断游戏是否结束
            game_end = False
            winning_role = ""
            reason = ""
            
            if spy_count == 0:
                # 所有卧底被淘汰，平民获胜
                game_end = True
                winning_role = ROLE_CIVILIAN
                reason = "所有卧底被淘汰"
                logger.info(f"房间 {room_id} 游戏结束: 平民获胜，所有卧底被淘汰")
            elif spy_count >= civilian_count:
                # 卧底数量超过或等于平民数量，卧底获胜
                game_end = True
                winning_role = ROLE_SPY
                reason = "卧底数量已经不少于平民数量"
                logger.info(f"房间 {room_id} 游戏结束: 卧底获胜，卧底数量({spy_count})不少于平民数量({civilian_count})")
            else:
                logger.info(f"房间 {room_id} 游戏继续: 卧底数量({spy_count}) < 平民数量({civilian_count})")
            
            result = {
                "game_end": game_end,
                "winning_role": winning_role,
                "reason": reason
            }
            
            logger.info(f"房间 {room_id} 游戏结束检查结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"检查游戏结束条件时出错: {str(e)}", exc_info=True)
            return {
                "game_end": False,
                "winning_role": "",
                "reason": f"检查出错: {str(e)}"
            }

    async def broadcast_game_result(self, room_id: str, game_end_result: Dict[str, Any]) -> None:
        """
        广播游戏结果并清理房间数据
        
        Args:
            room_id: 房间ID
            game_end_result: 游戏结束结果
        """
        try:
            # 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            
            # 获取所有玩家角色信息
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            all_roles = await self.redis_client.hgetall(role_key)
            
            # 准备角色信息
            player_roles = []
            civilian_ids = []
            spy_ids = []
            
            for player_id, role in all_roles.items():
                player_name = "未知玩家"
                
                if player_id.startswith("llm_player_"):
                    player_name = f"AI玩家_{player_id.replace('llm_player_', '')}"
                else:
                    player_data = await self.redis_client.hgetall(f"user:{player_id}")
                    if player_data:
                        player_name = player_data.get("username", "未知玩家")
                
                if role == ROLE_CIVILIAN:
                    civilian_ids.append(player_id)
                elif role == ROLE_SPY:
                    spy_ids.append(player_id)
                        
                player_roles.append({
                    "id": player_id,
                    "username": player_name,
                    "role": role
                })
                
            # 设置获胜方消息
            winning_role = game_end_result.get("winning_role", ROLE_CIVILIAN)
            winning_message = f"{'平民' if winning_role == ROLE_CIVILIAN else '卧底'}阵营获胜！"
            
            # 获取当前回合数
            current_round = int(room_data.get("current_round", "1"))
            
            # 构建游戏结束消息
            game_end_message = {
                "type": "game_end",
                "winning_role": winning_role,
                "message": winning_message,
                "players": player_roles,
                "roles": all_roles,
                "civilian_ids": civilian_ids,
                "spy_ids": spy_ids,
                "rounds": current_round,
                "timestamp": int(time.time() * 1000)
            }
            
            # 广播游戏结束消息
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=game_end_message,
                is_special=False
            )
            
            # 发送系统消息通知
            system_message = {
                "type": "system",
                "content": f"游戏结束，{winning_message}",
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=system_message,
                is_special=False
            )
            
            logger.info(f"已广播游戏结果: 房间 {room_id}，获胜方: {winning_role}")
            
            # 清理房间游戏数据
            await self._cleanup_room_game_data(room_id)
            
        except Exception as e:
            logger.error(f"广播游戏结果失败: {str(e)}")

    async def _cleanup_room_game_data(self, room_id: str) -> None:
        """
        清理房间游戏相关数据
        
        Args:
            room_id: 房间ID
        """
        try:
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            
            # 获取当前轮次和回合数
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = room_data.get("current_round", "1")
            
            # 1. 更新房间状态为等待中
            update_fields = {
                "status": GAME_STATUS_WAITING,
                "current_phase": "",
                "current_round": "0",
                "god_id": "",
                "secret_chat_active": "false",
                "word_civilian": "",
                "word_spy": ""
            }
            await self.redis_client.hmset(room_key, update_fields)
            
            # 2. 清理准备用户集合
            ready_users_key = f"room:{room_id}:ready_users"
            await self.redis_client.delete(ready_users_key)
            
            # 3. 清理存活玩家集合
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            await self.redis_client.delete(alive_players_key)
            
            # 4. 清理角色分配
            roles_key = ROOM_ROLES_KEY_PREFIX % room_id
            await self.redis_client.delete(roles_key)
            
            # 5. 清理投票记录
            vote_key = f"room:{room_id}:votes:{current_round}"
            vote_count_key = f"room:{room_id}:vote_count:{current_round}"
            await self.redis_client.delete(vote_key)
            await self.redis_client.delete(vote_count_key)
            
            # 6. 清理秘密聊天投票
            secret_votes_key = f"room:{room_id}:secret_votes:{current_round}"
            await self.redis_client.delete(secret_votes_key)
            
            # 7. 清理轮询上帝状态
            poll_state_key = f"poll_state:{room_id}"
            await self.redis_client.delete(poll_state_key)
            
            # 8. 清理轮次发言者顺序
            round_speakers_key = f"room:{room_id}:round_speakers"
            await self.redis_client.delete(round_speakers_key)
            
            logger.info(f"房间 {room_id} 游戏数据已清理完成")
            
        except Exception as e:
            logger.error(f"清理房间 {room_id} 游戏数据失败: {str(e)}")

    async def handle_player_vote(self, room_id: str, voter_id: str, target_id: str) -> Dict[str, Any]:
        """
        处理玩家投票
        
        Args:
            room_id: 房间ID
            voter_id: 投票者ID
            target_id: 投票目标ID
            
        Returns:
            Dict包含处理结果
        """
        try:
            logger.info(f"处理玩家 {voter_id} 对 {target_id} 的投票，房间: {room_id}")
            
            # 检查当前游戏阶段
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            current_phase = await self.redis_client.hget(room_key, "current_phase")
            
            if current_phase != "voting":
                logger.warning(f"投票失败: 房间 {room_id} 当前不在投票阶段，当前阶段 {current_phase}")
                return {
                    "success": False,
                    "message": "当前不在投票阶段"
                }
            
            # 检查投票者是否存活
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            voters_exists = await self.redis_client.zrank(alive_players_key, voter_id)
            
            if voters_exists is None:
                logger.warning(f"投票失败: 投票者 {voter_id} 不是存活玩家")
                return {
                    "success": False,
                    "message": "你不是存活玩家，无法投票"
                }
            
            # 检查投票目标是否存活
            target_exists = await self.redis_client.zrank(alive_players_key, target_id)
            
            if target_exists is None:
                logger.warning(f"投票失败: 投票目标 {target_id} 不是存活玩家")
                return {
                    "success": False,
                    "message": "投票目标不是存活玩家"
                }
                
            # 检查是否投票给自己
            if voter_id == target_id:
                logger.warning(f"投票失败: 玩家 {voter_id} 试图投票给自己")
                return {
                    "success": False,
                    "message": "不能投票给自己"
                }
                
            # 获取当前轮次
            current_round = await self.redis_client.hget(room_key, "current_round")
            if not current_round:
                logger.error(f"投票失败: 房间 {room_id} 无法获取当前轮次")
                return {
                    "success": False,
                    "message": "游戏轮次数据错误"
                }
            
            # 投票记录键
            vote_key = f"room:{room_id}:votes:{current_round}"
            vote_count_key = f"room:{room_id}:vote_count:{current_round}"
            
            # 检查玩家是否已经投过票
            previous_vote = await self.redis_client.hget(vote_key, voter_id)
            
            if previous_vote:
                logger.info(f"玩家 {voter_id} 之前已经投票给 {previous_vote}，现在改投 {target_id}")
                
                # 减少之前投票目标的票数
                await self.redis_client.hincrby(vote_count_key, previous_vote, -1)
            
            # 记录玩家投票
            await self.redis_client.hset(vote_key, voter_id, target_id)
            
            # 增加投票目标的票数
            await self.redis_client.hincrby(vote_count_key, target_id, 1)
            
            logger.info(f"玩家 {voter_id} 成功投票给 {target_id}")
            
            # 获取投票人和目标的名称，用于广播
            voter_name = "未知玩家"
            target_name = "未知玩家"
            
            if voter_id.startswith("llm_player_"):
                voter_name = f"AI玩家_{voter_id.replace('llm_player_', '')}"
            else:
                voter_data = await self.redis_client.hgetall(f"user:{voter_id}")
                if voter_data:
                    voter_name = voter_data.get("username", "未知玩家")
            
            if target_id.startswith("llm_player_"):
                target_name = f"AI玩家_{target_id.replace('llm_player_', '')}"
            else:
                target_data = await self.redis_client.hgetall(f"user:{target_id}")
                if target_data:
                    target_name = target_data.get("username", "未知玩家")
            
            # 广播投票消息
            vote_message = {
                "type": "vote_cast",
                "voter_id": voter_id,
                "voter_name": voter_name,
                "target_id": target_id,
                "target_name": target_name,
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=vote_message,
                is_special=False
            )
            
            # 检查所有玩家是否都投过票了
            alive_players = await self.redis_client.zrange(alive_players_key, 0, -1, withscores=False)
            voted_players = await self.redis_client.hkeys(vote_key)
            
            logger.info(f"房间 {room_id} 投票状态: {len(voted_players)}/{len(alive_players)} 玩家已投票")
            
            if len(alive_players) == len(voted_players):
                logger.info(f"房间 {room_id} 所有玩家都已投票，提前结束投票")
                
                # 验证当前阶段仍为投票阶段
                current_phase = await self.redis_client.hget(room_key, "current_phase")
                if current_phase != "voting":
                    logger.warning(f"所有玩家都已投票，但当前阶段已不是投票阶段，而是 {current_phase}，取消结算")
                    return {
                        "success": True,
                        "message": f"成功投票给 {target_name}，但游戏阶段已改变"
                    }
                
                # 所有玩家都已投票，提前结束投票
                result = await self.tally_votes(room_id)
                
                if result["success"]:
                    eliminated_player_id = result.get("eliminated_player_id")
                    if eliminated_player_id:
                        logger.info(f"玩家 {eliminated_player_id} 被投票淘汰")
                        
                        # 淘汰玩家
                        await self.eliminate_player(room_id, eliminated_player_id)
                    else:
                        # 平局或无人投票，进入下一轮
                        logger.info(f"投票无结果，准备进入下一轮")
                        
                        reason = result.get("reason", "tie")
                        message_text = "投票平局，无人被淘汰" if reason == "tie" else "无人投票，游戏继续"
                        
                        # 广播投票结果
                        vote_result_message = {
                            "type": "vote_result",
                            "result": reason,
                            "message": message_text,
                            "timestamp": int(time.time() * 1000)
                        }
                        
                        await self.websocket_manager.broadcast_message(
                            invite_code=room_id,
                            message=vote_result_message,
                            is_special=False
                        )
                        
                        # 发送系统消息
                        system_message = {
                            "type": "system",
                            "content": message_text,
                            "timestamp": int(time.time() * 1000)
                        }
                        
                        await self.websocket_manager.broadcast_message(
                            invite_code=room_id,
                            message=system_message,
                            is_special=False
                        )
                        
                        # 检查游戏是否结束
                        game_end_result = await self.check_game_end_condition(room_id)
                        
                        if game_end_result["game_end"]:
                            # 游戏结束，广播游戏结果
                            await self.broadcast_game_result(room_id, game_end_result)
                        else:
                            # 游戏未结束，开始下一轮
                            logger.info(f"投票无结果且游戏未结束，房间 {room_id} 安全开始下一轮")
                            await self.redis_client.hset(room_key, "current_phase", "voting_ended")
                            asyncio.create_task(self._safe_start_next_round(room_id))
                else:
                    logger.error(f"统计投票结果失败: {result.get('message', '未知错误')}")
                    # 如果出错，尝试继续游戏
                    try:
                        # 检查游戏是否应该结束
                        game_end_result = await self.check_game_end_condition(room_id)
                        if game_end_result["game_end"]:
                            # 游戏结束，广播游戏结果
                            await self.broadcast_game_result(room_id, game_end_result)
                        else:
                            # 游戏未结束，强制开始下一轮
                            logger.warning(f"投票统计失败，尝试强制开始新回合")
                            await self.redis_client.hset(room_key, "current_phase", "voting_error")
                            asyncio.create_task(self._safe_start_next_round(room_id))
                    except Exception as e:
                        logger.error(f"处理投票出错后尝试继续游戏失败: {str(e)}", exc_info=True)
            
            # 返回投票成功
            return {
                "success": True,
                "message": f"成功投票给 {target_name}"
            }
            
        except Exception as e:
            logger.error(f"处理玩家投票失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"投票处理失败: {str(e)}"
            }

    async def tally_votes(self, room_id: str) -> Dict[str, Any]:
        """
        统计投票结果
        
        Args:
            room_id: 房间ID
        """
        try:
            # 1. 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = room_data.get("current_round", "1")
            
            # 2. 获取投票结果
            vote_key = f"room:{room_id}:votes:{current_round}"
            votes = await self.redis_client.hgetall(vote_key)
            
            # 3. 统计投票
            vote_count = {}
            for voter_id, target_id in votes.items():
                if voter_id.endswith("_time"):
                    continue
                vote_count[target_id] = vote_count.get(target_id, 0) + 1
            
            # 4. 确定被淘汰玩家
            eliminated_player_id = None
            max_votes = 0
            tied_players = []
            
            # 如果没有投票，直接返回成功但没有淘汰玩家
            if not vote_count:
                logger.info(f"房间 {room_id} 没有投票记录")
                return {
                    "success": True,
                    "eliminated_player_id": None,
                    "vote_count": {},
                    "reason": "no_votes"
                }
            
            # 找出最高票数
            for player_id, vote_num in vote_count.items():
                if vote_num > max_votes:
                    max_votes = vote_num
                    eliminated_player_id = player_id
                    tied_players = [player_id]
                elif vote_num == max_votes:
                    tied_players.append(player_id)
            
            # 如果有平票，随机选择一个
            if len(tied_players) > 1:
                logger.info(f"房间 {room_id} 投票平局: {tied_players}")
                eliminated_player_id = random.choice(tied_players)
                logger.info(f"平局随机选择淘汰: {eliminated_player_id}")
            
            logger.info(f"房间 {room_id} 投票结果: {vote_count}")
            
            return {
                "success": True,
                "eliminated_player_id": eliminated_player_id,
                "vote_count": vote_count,
                "tied_players": tied_players if len(tied_players) > 1 else []
            }
            
        except Exception as e:
            logger.error(f"统计投票结果失败: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }

    async def eliminate_player(self, room_id: str, player_id: str) -> None:
        """
        淘汰玩家
        
        Args:
            room_id: 房间ID
            player_id: 玩家ID
        """
        try:
            # 获取当前房间阶段，确保在正确的阶段
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            current_phase = await self.redis_client.hget(room_key, "current_phase")
            
            logger.info(f"淘汰玩家 {player_id} 开始，当前房间 {room_id} 阶段: {current_phase}")
            
            # 检查玩家是否在存活列表中
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            player_exists = await self.redis_client.zrank(alive_players_key, player_id)
            
            if player_exists is None:
                logger.warning(f"玩家 {player_id} 不在存活玩家列表中，无法淘汰")
                return
            
            # 1. 从存活玩家列表中移除
            await self.redis_client.zrem(alive_players_key, player_id)
            
            # 2. 获取玩家角色信息
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            player_role = await self.redis_client.hget(role_key, player_id)
            
            if not player_role:
                logger.warning(f"玩家 {player_id} 没有角色信息，使用默认角色civilian")
                player_role = ROLE_CIVILIAN
            
            # 获取玩家名称
            player_name = "未知玩家"
            if player_id.startswith("llm_player_"):
                player_name = f"AI玩家_{player_id.replace('llm_player_', '')}"
            else:
                player_data = await self.redis_client.hgetall(f"user:{player_id}")
                if player_data:
                    player_name = player_data.get("username", "未知玩家")
            
            # 3. 广播玩家被淘汰的消息
            elimination_message = {
                "type": "player_eliminated",
                "player_id": player_id,
                "player_name": player_name,
                "role": player_role,
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=elimination_message,
                is_special=False
            )
            
            # 系统消息通知
            role_text = "平民" if player_role == ROLE_CIVILIAN else "卧底" if player_role == ROLE_SPY else "上帝"
            system_message = {
                "type": "system",
                "content": f"{player_name} 被淘汰，身份是{role_text}",
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=system_message,
                is_special=False
            )
            
            logger.info(f"玩家 {player_id} ({player_name}) 被淘汰，身份是 {player_role}")
            
            # 4. 检查游戏是否结束
            game_end_result = await self.check_game_end_condition(room_id)
            
            # 5. 如果游戏未结束，启动遗言阶段
            if not game_end_result.get("game_end", False):
                # 获取房间配置的遗言时间
                room_data = await self.redis_client.get_room_basic_data(room_id)
                last_words_time = int(room_data.get("last_words_time", 10))
                
                # 清理之前可能残留的last_words_player
                if await self.redis_client.hget(room_key, "last_words_player"):
                    logger.warning(f"淘汰玩家时发现残留的last_words_player，移除它")
                    await self.redis_client.hdel(room_key, "last_words_player")
                
                # 广播遗言阶段开始的消息
                last_words_message = {
                    "type": "last_words_start",
                    "player_id": player_id,
                    "player_name": player_name,
                    "timeout": last_words_time,
                    "timestamp": int(time.time() * 1000)
                }
                
                await self.websocket_manager.broadcast_message(
                    invite_code=room_id,
                    message=last_words_message,
                    is_special=False
                )
                
                # 设置遗言阶段标记
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                await self.redis_client.hset(room_key, "last_words_player", player_id)
                
                logger.info(f"房间 {room_id} 进入遗言阶段，玩家 {player_id}")
                
                # 如果是AI玩家，自动生成遗言
                if player_id.startswith("llm_player_"):
                    # 使用异步任务处理AI遗言，避免阻塞主流程
                    ai_task = asyncio.create_task(self.handle_ai_player_last_words(room_id, player_id, player_role))
                    # 添加任务完成回调，以便记录任务结果
                    ai_task.add_done_callback(
                        lambda t: logger.info(f"AI玩家 {player_id} 遗言任务完成: {'成功' if not t.exception() else f'失败: {t.exception()}'}")
                    )
                    logger.info(f"为AI玩家 {player_id} 生成遗言的任务已创建")
                
                # 设置遗言超时任务
                timeout_task = asyncio.create_task(self._handle_last_words_timeout(room_id, last_words_time))
                timeout_task.add_done_callback(
                    lambda t: logger.info(f"遗言超时任务完成: {'成功' if not t.exception() else f'失败: {t.exception()}'}")
                )
                
                logger.info(f"玩家 {player_id} 的遗言阶段开始，时间为 {last_words_time} 秒")
            else:
                # 游戏结束，广播游戏结果
                await self.broadcast_game_result(room_id, game_end_result)
        
        except Exception as e:
            logger.error(f"淘汰玩家 {player_id} 失败: {str(e)}")

    async def handle_ai_player_last_words(self, room_id: str, ai_player_id: str, role: str) -> None:
        """
        处理AI玩家的遗言生成
        
        Args:
            room_id: 房间ID
            ai_player_id: AI玩家ID
            role: AI玩家角色
        """
        try:
            logger.info(f"开始为AI玩家 {ai_player_id} 生成遗言")
            
            # 检查当前房间阶段
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            current_phase = await self.redis_client.hget(room_key, "current_phase")
            last_words_player = await self.redis_client.hget(room_key, "last_words_player")
            
            logger.info(f"AI玩家遗言生成时的房间阶段: {current_phase}, 允许遗言的玩家: {last_words_player}")
            
            # 验证当前是否是遗言阶段且AI是遗言玩家
            if current_phase != "last_words":
                logger.warning(f"AI玩家 {ai_player_id} 尝试生成遗言，但当前阶段 {current_phase} 不是last_words")
                await self.redis_client.hset(room_key, "current_phase", "last_words")
            
            if last_words_player != ai_player_id:
                logger.warning(f"AI玩家 {ai_player_id} 尝试生成遗言，但当前遗言玩家是 {last_words_player}")
                if not last_words_player:
                    await self.redis_client.hset(room_key, "last_words_player", ai_player_id)
            
            # 延迟一小段时间，让玩家能看到遗言阶段开始的提示
            await asyncio.sleep(3)
            
            # 获取游戏历史记录用于上下文
            chat_history = await self.message_service.get_room_messages(room_id, limit=20)
            # 反转顺序获取最近的消息
            chat_history = chat_history[::-1]
            
            # 准备游戏信息
            room_data = await self.redis_client.get_room_basic_data(room_id)
            
            # 获取所有玩家角色
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            all_roles = await self.redis_client.hgetall(role_key)
            
            # 获取存活玩家列表
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            alive_players = await self.redis_client.zrange(alive_players_key, 0, -1, withscores=False)
            
            # 准备AI需要的游戏信息
            game_info = {
                "room_id": room_id,
                "current_round": room_data.get("current_round", "1"),
                "ai_player_id": ai_player_id,
                "ai_player_role": role,
                "all_roles": all_roles,
                "alive_players": alive_players,
                "civilian_word": room_data.get("word_civilian", ""),
                "spy_word": room_data.get("word_spy", ""),
                "chat_history": chat_history
            }
            
            # 设置默认遗言，以防LLM生成失败
            default_last_words = "我怀疑玩家2和玩家3，因为他们描述过于模糊且相互矛盾。特别是对颜色和形状的表述与其他人完全不同。请仔细观察他们的用词！"
            
            # 调用LLM生成遗言，设置超时机制
            last_words_content = ""
            llm_success = False
            
            if self.llm_pipeline:
                try:
                    # 创建一个空的消息列表传递给LLM
                    messages = []
                    for msg in chat_history:
                        message_obj = {
                            "id": msg.get("id", ""),
                            "room_id": room_id,
                            "user_id": msg.get("user_id", ""),
                            "username": msg.get("username", ""),
                            "content": msg.get("content", ""),
                            "timestamp": msg.get("timestamp", 0),
                            "is_system": msg.get("type") == "system"  # 修复这里，使用msg.get("type")判断而不是msg.is_system
                        }
                        messages.append(message_obj)
                    
                    # 设置超时，避免LLM调用无限等待
                    async def get_llm_response():
                        result = ""
                        try:
                            async for chunk in self.llm_pipeline.chat_completion(
                                messages=messages,
                                current_message="请以被淘汰玩家的身份生成一段遗言",
                                context_type="last_words",
                                game_info=game_info
                            ):
                                result += chunk
                            return result
                        except Exception as llm_error:
                            logger.error(f"LLM生成遗言出错: {str(llm_error)}")
                            return ""
                    
                    # 使用asyncio.wait_for设置超时
                    last_words_content = await asyncio.wait_for(get_llm_response(), timeout=10.0)
                    
                    if last_words_content:
                        llm_success = True
                        logger.info(f"AI玩家 {ai_player_id} 遗言生成成功: {last_words_content}")
                    else:
                        logger.warning(f"LLM为AI玩家 {ai_player_id} 返回了空遗言，使用默认遗言")
                        last_words_content = default_last_words
                except asyncio.TimeoutError:
                    logger.warning(f"为AI玩家 {ai_player_id} 生成遗言超时，使用默认遗言")
                    last_words_content = default_last_words
                except Exception as e:
                    logger.error(f"遗言生成过程中出错: {str(e)}")
                    last_words_content = default_last_words
            else:
                logger.error(f"LLM管道未配置，无法为AI玩家 {ai_player_id} 生成遗言")
                last_words_content = default_last_words
                
            # 通过handle_last_words函数处理AI遗言，保持统一的逻辑
            try:
                logger.info(f"AI玩家 {ai_player_id} 发送遗言: {last_words_content}")
                await self.handle_last_words(
                    room_id=room_id,
                    player_id=ai_player_id,
                    message={"content": last_words_content}
                )
                logger.info(f"AI玩家 {ai_player_id} 遗言处理成功")
            except Exception as e:
                logger.error(f"处理AI玩家 {ai_player_id} 遗言失败: {str(e)}")
                # 尝试错误恢复
                try:
                    logger.warning(f"AI遗言错误恢复：房间 {room_id}，尝试进入下一轮")
                    await self.redis_client.hset(room_key, "current_phase", "last_words")
                    await self.redis_client.hdel(room_key, "last_words_player")
                    asyncio.create_task(self._safe_start_next_round(room_id))
                except Exception as recovery_error:
                    logger.error(f"AI遗言错误恢复失败: {str(recovery_error)}")
        except Exception as e:
            logger.error(f"为AI玩家 {ai_player_id} 生成遗言失败: {str(e)}", exc_info=True)
            try:
                # 尝试错误恢复
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                logger.warning(f"AI玩家遗言整体错误恢复：房间 {room_id}，直接进入下一轮")
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                await self.redis_client.hdel(room_key, "last_words_player")
                asyncio.create_task(self._safe_start_next_round(room_id))
            except Exception as recover_e:
                logger.error(f"AI玩家遗言整体错误恢复失败: {str(recover_e)}", exc_info=True)

    async def _handle_last_words_timeout(self, room_id: str, timeout_seconds: int) -> None:
        """
        处理遗言超时
        
        Args:
            room_id: 房间ID
            timeout_seconds: 超时时间（秒）
        """
        try:
            # 等待指定的超时时间
            await asyncio.sleep(timeout_seconds)
            
            logger.info(f"房间 {room_id} 遗言时间已到，结束遗言阶段")
            
            # 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            last_words_player = room_data.get("last_words_player")
            current_phase = room_data.get("current_phase", "")
            
            logger.info(f"房间 {room_id} 遗言超时，当前阶段: {current_phase}, 最后发言玩家: {last_words_player}")
            
            # 如果当前阶段不是遗言阶段，记录并修复
            if current_phase != "last_words":
                logger.warning(f"房间 {room_id} 遗言超时，但当前阶段 {current_phase} 不是last_words，尝试修复")
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                current_phase = "last_words"
            
            # 广播遗言阶段结束消息
            end_message = {
                "type": "last_words_phase_end",
                "player_id": last_words_player,
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=end_message,
                is_special=False
            )
            
            # 清除遗言玩家信息
            await self.redis_client.hdel(room_key, "last_words_player")
            
            # 等待1.5秒，保持与正常遗言流程一致
            logger.info(f"等待1.5秒后为房间 {room_id} 开始下一轮")
            await asyncio.sleep(1.5)
            
            # 记录当前状态
            logger.info(f"等待结束，当前房间 {room_id} 阶段: {current_phase}")
            
            # 检查游戏是否结束
            game_end_result = await self.check_game_end_condition(room_id)
            
            if game_end_result["game_end"]:
                # 游戏结束，广播游戏结果
                logger.info(f"游戏结束，广播游戏结果: {game_end_result}")
                await self.broadcast_game_result(room_id, game_end_result)
            else:
                # 游戏未结束，进入下一轮
                logger.info(f"游戏未结束，房间 {room_id} 开始进入下一轮")
                
                # 确保阶段设置为last_words，以便正确进入下一轮
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                
                # 添加额外日志跟踪
                logger.info(f"遗言超时处理：设置房间 {room_id} 阶段为last_words后准备进入下一轮")
                
                # 创建一个新的任务来处理下一轮，避免阻塞当前流程
                asyncio.create_task(self._safe_start_next_round(room_id))
        except asyncio.CancelledError:
            logger.info(f"房间 {room_id} 遗言超时任务被取消")
        except Exception as e:
            logger.error(f"处理遗言超时任务失败: {str(e)}", exc_info=True)
            # 出错时尝试进入下一轮
            try:
                # 获取当前阶段
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                current_phase = await self.redis_client.hget(room_key, "current_phase")
                
                logger.info(f"遗言出错处理: 当前房间 {room_id} 阶段: {current_phase}")
                
                # 尝试恢复并进入下一轮
                logger.warning(f"遗言超时错误恢复：房间 {room_id}，尝试进入下一轮")
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                await self.redis_client.hdel(room_key, "last_words_player")
                asyncio.create_task(self._safe_start_next_round(room_id))
            except Exception as e2:
                logger.error(f"处理遗言错误后尝试进入下一轮失败: {str(e2)}", exc_info=True)

    async def handle_last_words(self, room_id: str, player_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理玩家发送的遗言
        
        Args:
            room_id: 房间ID
            player_id: 玩家ID
            message: 遗言内容
            
        Returns:
            Dict包含处理结果
        """
        try:
            # 1. 检查该玩家是否有权限发送遗言
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            last_words_player = room_data.get("last_words_player")
            current_phase = room_data.get("current_phase", "")
            
            logger.info(f"处理玩家 {player_id} 的遗言, 当前房间阶段: {current_phase}, 允许遗言的玩家: {last_words_player}")
            
            # 如果当前阶段不是遗言阶段，记录并尝试修复
            if current_phase != "last_words":
                logger.warning(f"玩家 {player_id} 发送遗言时，当前阶段 {current_phase} 不是last_words，尝试修复")
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                current_phase = "last_words"
            
            if not last_words_player or last_words_player != player_id:
                logger.warning(f"玩家 {player_id} 无权发送遗言，当前遗言玩家为 {last_words_player}")
                return {
                    "success": False,
                    "message": "你没有权限发送遗言"
                }
            
            # 2. 检查消息内容
            content = message.get("content", "").strip()
            if not content:
                return {
                    "success": False,
                    "message": "遗言内容不能为空"
                }
            
            # 3. 获取玩家信息
            player_name = "未知玩家"
            if player_id.startswith("llm_player_"):
                player_name = f"AI玩家_{player_id.replace('llm_player_', '')}"
            else:
                player_data = await self.redis_client.hgetall(f"user:{player_id}")
                if player_data:
                    player_name = player_data.get("username", "未知玩家")
            
            # 4. 构建遗言消息
            last_words_message = {
                "type": "last_words",
                "user_id": player_id,
                "username": player_name,
                "content": content,
                "timestamp": int(time.time() * 1000)
            }
            
            # 5. 广播遗言消息
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=last_words_message,
                is_special=False
            )
            
            # 6. 记录到聊天历史
            if self.message_service:
                # 使用process_message方法而不是add_message_to_history
                await self.message_service.process_message({
                    "type": "system",
                    "user_id": player_id,
                    "room_id": room_id,
                    "username": player_name,
                    "content": f"[遗言] {content}",
                    "timestamp": int(time.time() * 1000),
                    "is_system": True
                })
            
            logger.info(f"玩家 {player_id} 发送了遗言: {content}")
            
            # 7. 提前结束遗言阶段
            # 清除遗言玩家信息
            await self.redis_client.hdel(room_key, "last_words_player")
            
            # 广播遗言阶段结束消息
            end_message = {
                "type": "last_words_phase_end",
                "player_id": player_id,
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=end_message,
                is_special=False
            )
            
            logger.info(f"已广播玩家 {player_id} 的遗言阶段结束消息")
            
            # 等待1.5秒，让玩家有时间阅读遗言
            logger.info(f"等待1.5秒后为房间 {room_id} 开始下一轮")
            await asyncio.sleep(1.5)
            
            # 确保当前阶段为last_words时才进入下一轮
            logger.info(f"等待结束，当前房间 {room_id} 阶段: {current_phase}")
            
            # 无论当前阶段是什么，都强制进行游戏结束检查和下一轮处理
            # 检查游戏是否结束
            game_end_result = await self.check_game_end_condition(room_id)
            
            if game_end_result["game_end"]:
                # 游戏结束，广播游戏结果
                logger.info(f"游戏结束，广播游戏结果: {game_end_result}")
                await self.broadcast_game_result(room_id, game_end_result)
            else:
                # 游戏未结束，进入下一轮
                logger.info(f"游戏未结束，房间 {room_id} 开始进入下一轮")
                
                # 确保阶段设置为last_words，以便正确进入下一轮
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                
                # 添加额外日志跟踪
                logger.info(f"设置房间 {room_id} 阶段为last_words后准备进入下一轮")
                
                # 创建一个新的任务来处理下一轮，避免阻塞当前流程
                asyncio.create_task(self._safe_start_next_round(room_id))
                
            return {
                "success": True,
                "message": "遗言发送成功"
            }
            
        except Exception as e:
            logger.error(f"处理玩家遗言失败: {str(e)}", exc_info=True)
            # 尝试错误恢复
            try:
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                logger.warning(f"处理遗言错误恢复：房间 {room_id}，尝试进入下一轮")
                await self.redis_client.hset(room_key, "current_phase", "last_words")
                await self.redis_client.hdel(room_key, "last_words_player")
                asyncio.create_task(self._safe_start_next_round(room_id))
            except Exception as recovery_error:
                logger.error(f"遗言错误恢复失败: {str(recovery_error)}")
            
            return {
                "success": False,
                "message": "遗言处理失败，但游戏将继续"
            }
    
    async def _safe_start_next_round(self, room_id: str) -> None:
        """
        安全地开始下一轮游戏，带有额外的错误处理
        
        Args:
            room_id: 房间ID
        """
        try:
            logger.info(f"安全启动下一轮: 房间 {room_id}")
            
            # 先检查房间是否存在
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_exists = await self.redis_client.exists(room_key)
            
            if not room_exists:
                logger.error(f"安全启动下一轮失败: 房间 {room_id} 不存在")
                return
                
            # 检查游戏状态
            game_status = await self.redis_client.hget(room_key, "game_status")
            if game_status != GAME_STATUS_PLAYING:
                logger.warning(f"安全启动下一轮: 房间 {room_id} 当前游戏状态不是进行中 ({game_status})，不启动下一轮")
                return
                
            # 检查存活玩家是否足够
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            alive_players_count = await self.redis_client.zcard(alive_players_key)
            
            if alive_players_count < 2:
                logger.warning(f"安全启动下一轮: 房间 {room_id} 存活玩家数量不足 ({alive_players_count})，检查游戏结束条件")
                game_end_result = await self.check_game_end_condition(room_id)
                if game_end_result["game_end"]:
                    await self.broadcast_game_result(room_id, game_end_result)
                return
            
            # 正常启动下一轮
            await self.start_next_round(room_id)
        except Exception as e:
            logger.error(f"安全启动下一轮失败: {str(e)}", exc_info=True)
            # 尝试恢复游戏状态
            try:
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                # 获取当前回合
                current_round = await self.redis_client.hget(room_key, "current_round")
                if current_round:
                    next_round = int(current_round) + 1
                    logger.warning(f"恢复措施: 直接设置房间 {room_id} 进入回合 {next_round} 并开始发言阶段")
                    await self.redis_client.hset(room_key, "current_round", str(next_round))
                    await self.redis_client.hset(room_key, "current_phase", "speaking")
                    
                    # 清理任何残留数据
                    round_speakers_key = f"room:{room_id}:round_speakers"
                    await self.redis_client.delete(round_speakers_key)
                    
                    # 尝试直接开始发言阶段
                    asyncio.create_task(self.start_speaking_phase(room_id))
            except Exception as recovery_error:
                logger.error(f"恢复游戏状态失败: {str(recovery_error)}", exc_info=True)

    async def start_next_round(self, room_id: str) -> None:
        """
        开始下一轮游戏
        
        Args:
            room_id: 房间ID
        """
        try:
            # 1. 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = int(room_data.get("current_round", "1"))
            max_rounds = int(room_data.get("max_rounds", "5"))
            current_phase = room_data.get("current_phase", "")
            
            # 打印详细信息以便调试
            logger.info(f"开始下一轮游戏: 房间 {room_id}, 当前回合 {current_round}, 最大回合 {max_rounds}, 当前阶段 {current_phase}")
            
            # 2. 检查是否达到最大回合数
            if current_round >= max_rounds:
                logger.info(f"房间 {room_id} 已达到最大回合数 {max_rounds}，宣布平局")
                await self.broadcast_draw_result(room_id)
                return
                
            # 3. 增加回合数
            next_round = current_round + 1
            await self.redis_client.hset(room_key, "current_round", str(next_round))
            
            # 4. 重置发言顺序
            round_speakers_key = f"room:{room_id}:round_speakers"
            await self.redis_client.delete(round_speakers_key)
            
            # 5. 清理之前阶段的残留数据
            # 确保没有残留的last_words_player
            if await self.redis_client.hget(room_key, "last_words_player"):
                logger.warning(f"房间 {room_id} 开始新回合时发现残留的last_words_player，移除它")
                await self.redis_client.hdel(room_key, "last_words_player")
            
            # 确保投票数据被清理
            vote_key = ROOM_VOTES_KEY_PREFIX % room_id
            if await self.redis_client.exists(vote_key):
                logger.warning(f"房间 {room_id} 开始新回合时发现残留的投票数据，清理它")
                await self.redis_client.delete(vote_key)
            
            # 6. 开始发言阶段
            logger.info(f"房间 {room_id} 开始第 {next_round} 轮游戏的发言阶段")
            await self.start_speaking_phase(room_id)
            
            # 7. 广播新回合开始消息
            new_round_message = {
                "type": "new_round_start",
                "round": next_round,
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=new_round_message,
                is_special=False
            )
            
            logger.info(f"房间 {room_id} 开始第 {next_round} 轮游戏，广播消息成功")
            
        except Exception as e:
            logger.error(f"开始下一轮游戏失败: {str(e)}", exc_info=True)
            # 尝试恢复游戏流程
            try:
                room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                current_round = await self.redis_client.hget(room_key, "current_round")
                
                if current_round:
                    next_round = int(current_round) + 1
                    logger.warning(f"错误恢复: 设置房间 {room_id} 进入回合 {next_round} 并重新尝试开始发言阶段")
                    await self.redis_client.hset(room_key, "current_round", str(next_round))
                    await self.redis_client.hset(room_key, "current_phase", "speaking")
                    
                    # 重置发言顺序
                    round_speakers_key = f"room:{room_id}:round_speakers"
                    await self.redis_client.delete(round_speakers_key)
                    
                    # 直接开始发言阶段
                    asyncio.create_task(self.start_speaking_phase(room_id))
            except Exception as recovery_error:
                logger.error(f"恢复游戏流程失败: {str(recovery_error)}", exc_info=True)
            
    async def broadcast_draw_result(self, room_id: str) -> None:
        """
        广播平局结果并清理房间数据
        
        Args:
            room_id: 房间ID
        """
        try:
            # 获取房间基本信息
            room_key = f"{ROOM_KEY_PREFIX}{room_id}"
            room_data = await self.redis_client.get_room_basic_data(room_id)
            
            # 获取所有玩家角色信息
            role_key = ROOM_ROLES_KEY_PREFIX % room_id
            all_roles = await self.redis_client.hgetall(role_key)
            
            # 准备角色信息
            player_roles = []
            civilian_ids = []
            spy_ids = []
            
            for player_id, role in all_roles.items():
                player_name = "未知玩家"
                
                if player_id.startswith("llm_player_"):
                    player_name = f"AI玩家_{player_id.replace('llm_player_', '')}"
                else:
                    player_data = await self.redis_client.hgetall(f"user:{player_id}")
                    if player_data:
                        player_name = player_data.get("username", "未知玩家")
                
                if role == ROLE_CIVILIAN:
                    civilian_ids.append(player_id)
                elif role == ROLE_SPY:
                    spy_ids.append(player_id)
                        
                player_roles.append({
                    "id": player_id,
                    "username": player_name,
                    "role": role
                })
            
            # 获取当前回合数
            current_round = int(room_data.get("current_round", "5"))
            
            # 设置平局消息 - 使用game_end格式
            game_end_message = {
                "type": "game_end",
                "winning_role": "draw",  # 平局
                "message": f"游戏平局！已达到最大回合数 {room_data.get('max_rounds', '5')}",
                "players": player_roles,
                "roles": all_roles,
                "civilian_ids": civilian_ids,
                "spy_ids": spy_ids,
                "rounds": current_round,
                "timestamp": int(time.time() * 1000)
            }
            
            # 广播游戏结束消息
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=game_end_message,
                is_special=False
            )
            
            # 发送系统消息通知
            system_message = {
                "type": "system",
                "content": f"游戏平局！已达到最大回合数 {room_data.get('max_rounds', '5')}",
                "timestamp": int(time.time() * 1000)
            }
            
            await self.websocket_manager.broadcast_message(
                invite_code=room_id,
                message=system_message,
                is_special=False
            )
            
            logger.info(f"房间 {room_id} 游戏平局，已广播结果")
            
            # 清理房间游戏数据
            await self._cleanup_room_game_data(room_id)
            
        except Exception as e:
            logger.error(f"广播平局结果失败: {str(e)}")

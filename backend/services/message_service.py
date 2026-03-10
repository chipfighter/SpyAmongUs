"""
services: message_service

Description:
    主要包含和消息直接相关的处理

Notes:
    service层返回统一的格式:
    Dict[str, Any]，包含以下字段：
    - success: bool，操作是否成功
    - message: str，操作结果消息
    - data: Optional[Dict]，返回的数据（如果有）

Methods:
    - AI消息的处理
    - 处理websocket发送过来的消息、处理secret_channel发送的消息
    - 服务端的系统消息发送处理
    - 获取房间的消息、secret_channel消息
"""

from typing import Dict, Any, Optional, Set, List
from models.message import Message
from utils.logger_utils import get_logger
import time
import json
from utils.message_queue_manager import MessageQueueManager
from utils.ai_lock_manager import AIStorageLockManager
import uuid
import re
import asyncio

logger = get_logger(__name__)

class MessageService:
    def __init__(self, redis_client, websocket_manager, llm_service):
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        self.llm_service = llm_service
        # 消息队列
        self.message_queue_manager = MessageQueueManager(redis_client)
        # 每个房间的AI锁
        self.ai_storage_lock_manager = AIStorageLockManager(redis_client)

    async def _validate_message_format(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证消息格式"""
        logger.info(f"验证消息格式: {message_data}")
        
        # 验证是否是字典
        if not isinstance(message_data, dict):
            logger.error("消息不是JSON对象")
            return {
                "valid": False,
                "message": "消息必须是JSON对象"
            }

        # 验证content字段
        content = message_data.get("content")
        if content is None:
            logger.error("消息缺少content字段")
            return {
                "valid": False,
                "message": "消息必须包含content字段"
            }

        if not isinstance(content, str) or not content.strip():
            logger.error("消息内容为空")
            return {
                "valid": False,
                "message": "消息内容不能为空"
            }
            
        # 验证必要字段
        required_fields = ["user_id", "room_id"]
        for field in required_fields:
            if field not in message_data:
                logger.error(f"消息缺少必要字段: {field}")
                return {
                    "valid": False,
                    "message": f"消息必须包含{field}字段"
                }

        # 消息类型验证
        msg_type = message_data.get("type")
        if msg_type is not None and msg_type not in ["chat", "secret", "system", "last_words"]:
            logger.error(f"无效的消息类型: {msg_type}")
            return {
                "valid": False,
                "message": "消息类型无效"
            }

        logger.info("消息格式验证通过")
        return {
            "valid": True,
            "message": "消息格式有效"
        }


    # 统一消息处理
    async def process_message(self, message_data: dict) -> dict:
        """
        统一消息处理

        Notes:
            所有房间内普通消息都经过该函数（secret_channel情况除外）
            如果有@情况和AI相关的消息处理是另外单独逻辑
        """
        try:
            logger.info(f"开始处理消息: {message_data}")

            # 验证消息格式
            validation = await self._validate_message_format(message_data)
            if not validation["valid"]:
                logger.error(f"消息格式验证失败: {validation['message']}")
                return {"success": False, "message": validation["message"]}

            room_id = message_data.get("room_id")
            user_id = message_data.get("user_id")

            if not room_id:
                logger.error("消息缺少room_id字段")
                return {"success": False, "message": "消息缺少room_id字段"}

            if not user_id:
                logger.error("消息缺少user_id字段")
                return {"success": False, "message": "消息缺少user_id字段"}

            logger.info(f"将消息添加到Redis队列: {message_data}")
            await self.message_queue_manager.add_message(room_id, message_data)

            # 启动Redis队列处理器
            await self.message_queue_manager.start_queue_processor(
                room_id,
                self._process_message
            )

            return {"success": True, "message": "Message queued successfully"}

        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            return {"success": False, "message": f"Failed to process message: {str(e)}"}

    async def _process_message(self, room_id: str, message_data: dict) -> None:
        """
        处理来自Redis消息队列的消息

        Notes:
            内置消息预处理函数，重点处理AI相关的聊天消息+游戏不同阶段的分别调用
        """
        try:
            logger.info(f"处理来自Redis队列的消息: {message_data}")

            user_id = message_data.get("user_id")
            if not user_id:
                logger.error(f"消息缺少user_id字段: {message_data}")
                return

            # 获取当前游戏状态
            room_data = await self.redis_client.get_room_basic_data(room_id)
            game_started = room_data.get("status") == "playing"
            current_phase = room_data.get("current_phase", "")
            
            # 根据游戏阶段分发处理
            if game_started:
                if current_phase == "speaking":
                    # 发言阶段消息处理
                    await self._handle_speaking_phase_message(room_id, message_data, user_id)
                    return  # 如果已处理完毕，直接返回
                elif current_phase == "voting":
                    # 投票阶段消息处理
                    await self._handle_voting_phase_message(room_id, message_data, user_id)
                    return
                elif current_phase == "last_words":
                    # 遗言阶段消息处理
                    logger.info(f"遗言阶段消息处理: {message_data}")
                    
                    # 获取当前可以发送遗言的玩家ID
                    last_words_player = room_data.get("last_words_player")
                    
                    if last_words_player and last_words_player == user_id:
                        # 如果该用户有权发送遗言，处理消息
                        # 确保消息类型为last_words
                        message_data["type"] = "last_words"
                        
                        # 调用游戏服务处理遗言
                        if self.game_service:
                            # 确保消息包含room_id字段
                            message_data["room_id"] = room_id
                            await self.game_service.handle_last_words(
                                room_id=room_id,
                                player_id=user_id,
                                message=message_data
                            )
                            # 直接返回，避免重复处理
                            return
                        else:
                            logger.error("无法访问game_service，无法处理遗言")
                            # 退回到普通消息处理
                            await self._handle_normal_message(room_id, message_data, user_id)
                    else:
                        # 对于非遗言玩家的消息，直接当作普通消息处理
                        # 而不是忽略消息
                        logger.warning(f"用户 {user_id} 在遗言阶段但非其遗言轮次发言，当作普通消息处理")
                        await self._handle_normal_message(room_id, message_data, user_id)
                    
                    return
                elif current_phase == "secret_chat":
                    # 秘密聊天阶段消息处理 - TODO
                    logger.info("秘密聊天阶段消息处理功能尚未实现")
                    # 暂时使用默认消息处理
                    await self._handle_normal_message(room_id, message_data, user_id)
                    return

            # 检查是否是AI消息
            contains_ai_mention = False
            if "mentions" in message_data:
                logger.info(f"检查mentions字段: {message_data['mentions']}")
                # 检查mentions数组中是否有ai_assistant
                contains_ai_mention = any(mention.get('id') == 'ai_assistant' for mention in message_data["mentions"])

            if contains_ai_mention or message_data.get('ai_type'):
                logger.info("检测到AI提及，尝试获取AI存储锁")
                # 获取AI存储锁
                lock_acquired = await self.ai_storage_lock_manager.acquire_storage_lock(room_id)
                if lock_acquired:
                    try:
                        # 锁获取成功，处理AI消息
                        logger.info(f"获取房间 {room_id} 的AI存储锁成功，处理AI消息")
                        await self.handle_ai_mention(room_id, message_data, user_id)
                    finally:
                        # 确保锁被释放
                        await self.ai_storage_lock_manager.release_storage_lock(room_id)
                else:
                    # 锁获取失败，AI正在处理中，将消息添加到待处理队列
                    logger.info(f"房间 {room_id} 的AI存储锁被占用，将消息添加到待处理队列")
                    await self.ai_storage_lock_manager.add_pending_message(room_id, {
                        "type": "ai_mention",
                        "message_data": message_data,
                        "user_id": user_id
                    })
            else:
                # 检查是否有AI处理正在进行
                is_locked = await self.ai_storage_lock_manager.is_storage_locked(room_id)
                
                # 立即获取用户信息准备广播
                user_info = await self.redis_client.hgetall(f"user:{user_id}")
                username = user_info.get("username", message_data.get("username", "Unknown"))
                content = message_data.get("content", "")
                
                # 不管是否有AI锁，都先广播消息到前端
                timestamp = int(time.time() * 1000)
                await self.websocket_manager.broadcast_message(invite_code=room_id, message={
                    "type": "chat",
                    "user_id": user_id,
                    "username": username,
                    "content": content,
                    "timestamp": timestamp,
                }, is_special=False)
                logger.info(f"已广播用户消息到房间 {room_id}")
                
                if is_locked:
                    # AI处理正在进行，将普通消息添加到待处理队列（仅为了保证存储顺序是时效性的）
                    logger.info(f"房间 {room_id} 的AI存储锁被占用，将普通消息添加到待处理队列（仅影响存储顺序，消息已广播）")
                    await self.ai_storage_lock_manager.add_pending_message(room_id, {
                        "type": "normal",
                        "message_data": message_data,
                        "user_id": user_id
                    })
                else:
                    # 普通消息直接处理（存储到Redis）
                    logger.info("检测到普通消息且无AI锁，直接处理并存储")
                    await self._handle_normal_message(room_id, message_data, user_id, skip_broadcast=True)  # 跳过广播，因为已经广播过了

        except Exception as e:
            logger.error(f"处理Redis队列消息失败: {str(e)}")


    # 普通消息处理
    async def _handle_normal_message(self, room_id: str, message_data: dict, user_id: str, skip_broadcast: bool = False):
        """处理普通消息"""
        try:
            logger.info(f"处理普通消息: {message_data}")
            content = message_data.get("content")

            # 获取用户信息
            user_info = await self.redis_client.hgetall(f"user:{user_id}")
            logger.info(f"获取到用户信息: {user_info}")
            username = user_info.get("username", message_data.get("username", "Unknown"))

            # 创建消息对象
            message = Message(
                user_id=user_id,
                username=username,
                content=content,
                timestamp=int(time.time() * 1000),
                is_system=False,
                round=message_data.get("round", "0")  # 使用消息中的round属性，默认为"0"
            )

            logger.info(f"创建消息对象: {message}")

            # 将消息对象转换为字典
            message_dict = message.dict()
            
            # 使用pipeline存储消息
            pipe = await self.redis_client.pipeline()
            pipe.lpush(f"room:{room_id}:messages", json.dumps(message_dict))
            pipe.expire(f"room:{room_id}:messages", 24 * 60 * 60)
            logger.info("执行Redis pipeline")
            await pipe.execute()

            # 广播消息到房间（如果skip_broadcast为True则跳过）
            if not skip_broadcast:
                logger.info(f"广播消息到房间 {room_id}")
                broadcast_message = {
                    "type": "chat",  # 明确指定消息类型
                    **message_dict   # 包含所有Message字段
                }
                await self.websocket_manager.broadcast_message(
                    invite_code=room_id, 
                    message=broadcast_message, 
                    is_special=False
                )
                logger.info("消息广播成功")
            else:
                logger.info(f"跳过广播到房间 {room_id}，消息已在队列处理前广播")

        except Exception as e:
            logger.error(f"处理普通消息失败: {str(e)}")
            # 尝试发送错误消息到前端
            try:
                await self.websocket_manager.broadcast_message(invite_code=room_id, message={
                    "type": "error",  # 明确指定错误消息类型
                    "message": f"处理消息失败: {str(e)}",
                    "timestamp": int(time.time() * 1000)
                }, is_special=False)
            except Exception as broadcast_error:
                logger.error(f"发送错误消息失败: {str(broadcast_error)}")


    async def handle_ai_mention(self, room_id: str, message_data: Dict[str, Any], user_id: str) -> None:
        """处理提及AI的消息(@的情况)"""
        try:
            # 生成时间戳作为唯一标识
            timestamp = int(time.time() * 1000)
            session_id = f"ai_session_{room_id}_{timestamp}"
            logger.info(f"创建新的AI会话: {session_id}")
            
            # 先广播用户的原始消息，让用户立即看到自己发送的消息，但不存储到Redis，等LLM处理完后再一起存储
            try:
                # 获取用户信息
                user_info = await self.redis_client.hgetall(f"user:{user_id}")
                logger.info(f"获取到用户信息: {user_info}")
                username = user_info.get("username", message_data.get("username", "Unknown"))
                
                # 广播原始消息
                await self.websocket_manager.broadcast_message(invite_code=room_id, message={
                    "type": "chat",
                    "user_id": user_id,
                    "username": username,
                    "content": message_data.get("content", ""),
                    "timestamp": timestamp,
                    "is_system": False,
                    "round": "0",
                    "mentions": message_data.get("mentions", []),
                    "ai_type": message_data.get("ai_type"),
                    "room_id": room_id
                }, is_special=False)
                logger.info("已广播用户原始消息")
                
                # 广播流式消息的预先消息，前端可以立即显示AI气泡和加载动画
                await self.websocket_manager.broadcast_message(invite_code=room_id, message={
                    "type": "ai_stream",
                    "is_start": True,
                    "is_end": False,
                    "content": "",  # 内容为空，前端会显示加载动画
                    "timestamp": timestamp + 1,  # 使用稍后的时间戳确保排序正确
                    "session_id": session_id
                }, is_special=False)
                logger.info("已广播AI准备状态，前端将显示加载动画")
                
            except Exception as e:
                logger.error(f"广播用户原始消息或AI准备状态失败: {str(e)}")
            
            # 获取聊天历史
            chat_history_dicts = await self.get_room_messages(room_id)
            
            # 将字典转换为Message对象
            chat_history = []
            for msg_dict in chat_history_dicts:
                try:
                    message = Message(
                        timestamp=msg_dict.get("timestamp", int(time.time() * 1000)),
                        user_id=msg_dict.get("user_id", ""),
                        username=msg_dict.get("username", "Unknown"),
                        content=msg_dict.get("content", ""),
                        is_system=msg_dict.get("type") == "system"
                    )
                    chat_history.append(message)
                except Exception as e:
                    logger.error(f"转换消息对象失败: {str(e)}")
                    continue
            
            # 初始化一个空字符串来存储完整的AI响应
            full_ai_response = ""
            
            # 设置是否是第一个块
            is_first_chunk = True
            
            # 跟踪上一个块的末尾字符，用于识别跨块的连续换行
            last_chunk_end = ""
            
            # 获取房间基本信息，包括speak_time
            room_data = await self.redis_client.get_room_basic_data(room_id)
            speak_time = int(room_data.get("speak_time", 60)) if room_data else 60
            
            # 构建游戏信息字典，包含发言时间限制
            game_info = {
                "speak_time": speak_time
            }
            
            # 调用LLM处理消息
            async for chunk in self.llm_service.chat_completion(
                messages=chat_history,
                current_message=message_data.get("content", ""),
                context_type="normal_chat",  # 默认使用普通聊天场景
                game_info=game_info  # 传递游戏信息
            ):
                # 累积完整响应
                full_ai_response += chunk

                # 处理跨块边界的连续换行问题
                check_str = last_chunk_end + chunk
                processed_chunk = re.sub(r'\n{3,}', '\n\n', check_str)
                
                # 只发送不包含上一个块末尾的内容
                if last_chunk_end and len(processed_chunk) > len(last_chunk_end):
                    processed_chunk = processed_chunk[len(last_chunk_end):]
                elif last_chunk_end:
                    # 如果处理后的内容小于或等于上一块结尾，说明全是重复内容
                    processed_chunk = ""
                
                # 更新末尾追踪（保存当前块的最后几个字符用于下次检查）
                last_chunk_end = chunk[-3:] if len(chunk) >= 3 else chunk
                
                # 构造流式消息
                chunk_timestamp = int(time.time() * 1000)
                stream_message = {
                    "timestamp": chunk_timestamp,
                    "type": "ai_stream",
                    "is_start": False,  # 修改为False，因为我们已经提前发送了开始消息
                    "is_end": False,
                    "content": processed_chunk,
                    "session_id": session_id  # 使用会话ID保持消息关联
                }
                
                # 广播到房间
                await self.websocket_manager.broadcast_message(invite_code=room_id, message=stream_message,
                                                               is_special=False)
                
                # 主动让出控制权给事件循环，允许其他任务（如广播普通消息）运行
                await asyncio.sleep(0)
                
                # 更新第一个块标志
                if is_first_chunk:
                    is_first_chunk = False
            
            # 发送最后一个空块作为结束标志
            end_timestamp = int(time.time() * 1000)
            end_message = {
                "timestamp": end_timestamp,
                "type": "ai_stream",
                "is_start": False,
                "is_end": True,
                "content": "",
                "session_id": session_id  # 使用同一个会话ID
            }
            
            await self.websocket_manager.broadcast_message(invite_code=room_id, message=end_message, is_special=False)
            
            # LLM处理完后，将用户消息和AI响应一起存储到Redis
            pipe = await self.redis_client.pipeline()
            
            # 1. 存储用户消息
            user_message = {
                "timestamp": timestamp,
                "user_id": user_id,
                "username": username,
                "content": message_data.get("content", "")
            }
            pipe.lpush(f"room:{room_id}:messages", json.dumps(user_message))
            
            # 2. 处理AI响应（去除llm多余的空行）并存储
            processed_ai_response = re.sub(r'\n{3,}', '\n\n', full_ai_response)

            ai_response_timestamp = int(time.time() * 1000)
            ai_message = {
                "timestamp": ai_response_timestamp,
                "user_id": "ai_assistant",
                "username": "AI助手",
                "content": processed_ai_response  # 存储处理后的AI响应
            }
            pipe.lpush(f"room:{room_id}:messages", json.dumps(ai_message))
            
            # 设置过期时间
            pipe.expire(f"room:{room_id}:messages", 24 * 60 * 60)  # 24小时过期
            await pipe.execute()
            
            logger.info(f"AI会话 {session_id} 处理完成，已存储消息到Redis")
            
            # 处理待处理消息队列
            await self._process_pending_messages(room_id)
            
        except Exception as e:
            logger.error(f"处理AI消息失败: {str(e)}")
            # 发送错误消息到前端
            await self.websocket_manager.broadcast_message(invite_code=room_id, message={
                "type": "error",
                "message": f"AI处理失败: {str(e)}",
                "timestamp": int(time.time() * 1000)
            }, is_special=False)

    async def _save_completed_ai_response(self, room_id: str, message_id: str, content: str, is_secret: bool = False) -> None:
        """
        保存完整的AI响应到Redis

        Args:
            room_id: 房间ID
            message_id: 消息ID
            content: 完整消息内容
            is_secret: 是否是秘密频道消息
        """
        try:
            # 创建AI消息对象
            message = Message.create_user_message(
                user_id="ai_assistant",
                username="AI助手",
                content=content
            )

            # 根据消息类型选择存储方式
            if is_secret:
                await self.redis_client.add_secret_channel_message(room_id, message)
            else:
                await self.redis_client.add_room_message(room_id, message)
                
        except Exception as e:
            logger.error(f"保存AI响应失败: {str(e)}")


    # 待处理消息队列部分
    async def _process_pending_messages(self, room_id: str):
        """处理待处理消息队列中的消息"""
        try:
            logger.info(f"开始处理房间 {room_id} 的待处理消息")

            # 处理所有待处理消息
            await self.ai_storage_lock_manager.process_pending_messages(room_id, self._process_single_pending_message)

        except Exception as e:
            logger.error(f"处理待处理消息失败: {str(e)}")

    async def _process_single_pending_message(self, message: dict):
        """处理单条待处理消息"""
        try:
            message_type = message.get("type")
            message_data = message.get("message_data")
            user_id = message.get("user_id")
            room_id = message_data.get("room_id")

            if not message_type or not message_data or not user_id or not room_id:
                logger.error(f"无效的待处理消息格式: {message}")
                return

            if message_type == "normal":
                # 处理普通消息，但跳过广播（因为在添加到待处理队列前已经广播过了）
                logger.info(f"处理待处理的普通消息: {message_data}")
                await self._handle_normal_message(room_id, message_data, user_id, skip_broadcast=True)

            if message_type == "ai_mention":
                logger.info(f"重新将AI消息添加到Redis队列: {message_data}")
                await self.message_queue_manager.add_message(room_id, message_data)
            
        except Exception as e:
            logger.error(f"处理单条待处理消息失败: {str(e)}")


    # 特殊消息处理
    async def process_secret_message(self, room_id: str, message_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        处理秘密频道消息
        
        Args:
            room_id: 房间ID
            message_data: 消息数据
            user_id: 用户ID
            
        Returns:
            Dict包含操作结果
        """
        try:
            # 验证消息格式
            validation = await self._validate_message_format(message_data)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"]
                }
            
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
                
            # 检查用户是否在该房间
            is_user_in_room = await self.redis_client.is_user_in_room(room_id, user_id)
            if not is_user_in_room:
                return {
                    "success": False,
                    "message": "用户不在该房间中"
                }
            
            # 获取用户信息
            user_data = await self.redis_client.get_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "无法获取用户信息"
                }
            
            # 获取目标用户集合
            target_users = message_data.get("target_users", [])
            if not target_users or not isinstance(target_users, list):
                return {
                    "success": False,
                    "message": "秘密消息必须指定目标用户"
                }
            
            # 检查目标用户是否全部在房间内
            for target_id in target_users:
                if not await self.redis_client.is_user_in_room(room_id, target_id):
                    return {
                        "success": False,
                        "message": f"目标用户 {target_id} 不在房间中"
                    }
            
            # 确保发送者也在目标用户列表中（可以看到自己发送的消息）
            if user_id not in target_users:
                target_users.append(user_id)
                
            # 创建消息对象
            username = user_data.get("username", "未知用户")
            content = message_data.get("content", "")
            
            message = Message.create_user_message(
                user_id=user_id,
                username=username,
                content=content
            )
            
            # 存储秘密消息
            storage_success = await self.redis_client.add_secret_channel_message(room_id, message)
            if not storage_success:
                return {
                    "success": False,
                    "message": "秘密消息存储失败"
                }
            
            # 广播到指定用户
            message_dict = message.dict()
            await self.websocket_manager.broadcast_message(invite_code=room_id,
                                                           message={**message_dict, "type": "secret"}, is_special=True,
                                                           target_users=set(target_users))
            
            return {
                "success": True,
                "message": "秘密消息发送成功",
                "data": message_dict
            }
            
        except Exception as e:
            logger.error(f"处理秘密消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"秘密消息处理失败: {str(e)}"
            }
    
    async def send_system_message(self, room_id: str, content: str, target_users: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        发送系统消息到房间
        
        Args:
            room_id: 房间ID
            content: 系统消息内容
            target_users: 目标用户集合，为None时广播给所有用户
            
        Returns:
            Dict包含操作结果
        """
        try:
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
            
            # 创建系统消息
            message = Message.create_system_message(content=content)
            
            # 将消息存储到Redis
            storage_success = await self.redis_client.add_room_message(room_id, message)
            if not storage_success:
                return {
                    "success": False,
                    "message": "消息存储失败"
                }
            
            # 广播系统消息
            message_dict = message.dict()
            message_dict["type"] = "system"  # 添加类型标识
            
            await self.websocket_manager.broadcast_message(invite_code=room_id, message=message_dict, is_special=False,
                                                           target_users=target_users)
            
            return {
                "success": True,
                "message": "系统消息发送成功",
                "data": message_dict
            }
            
        except Exception as e:
            logger.error(f"发送系统消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"系统消息发送失败: {str(e)}"
            }
            

    # 消息存储+获取
    async def get_room_messages(self, room_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取房间消息历史"""
        try:
            # 使用pipeline获取消息
            pipe = await self.redis_client.pipeline()
            pipe.lrange(f"room:{room_id}:messages", 0, limit - 1)
            pipe.ttl(f"room:{room_id}:messages")
            results = await pipe.execute()
            
            messages = results[0]
            ttl = results[1]
            
            # 如果消息即将过期，刷新过期时间
            if ttl < 12 * 60 * 60:  # 如果剩余时间小于12小时
                await self.redis_client.expire(f"room:{room_id}:messages", 24 * 60 * 60)
            
            # 解析消息
            return [json.loads(msg) for msg in messages]
            
        except Exception as e:
            logger.error(f"获取房间消息失败: {str(e)}")
            return []
    
    async def get_secret_room_messages(self, room_id: str, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        获取秘密频道消息历史
        
        Args:
            room_id: 房间ID
            user_id: 请求用户ID（用于权限验证）
            limit: 获取消息数量限制
            
        Returns:
            Dict包含操作结果和消息列表，消息列表已经保存在字典里，只不过处理需要符合service层的数据规范
        """
        try:
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
            
            # 检查用户是否在房间中
            is_user_in_room = await self.redis_client.is_user_in_room(room_id, user_id)
            if not is_user_in_room:
                return {
                    "success": False,
                    "message": "用户不在该房间中"
                }
            
            # 获取秘密频道消息
            messages = await self.redis_client.get_secret_channel_messages(room_id, limit)
            
            # 过滤消息（仅返回与该用户相关的消息）
            # 以用户ID作为筛选条件
            filtered_messages = []
            for message in messages:
                # 如果是该用户发送的消息或发给该用户的消息
                if message.user_id == user_id:
                    filtered_messages.append(message)
                    
            return {
                "success": True,
                "message": "获取秘密频道消息成功",
                "data": {
                    "messages": [message.dict() for message in filtered_messages]
                }
            }
            
        except Exception as e:
            logger.error(f"获取秘密频道消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"获取秘密频道消息失败: {str(e)}"
            }

    async def _handle_speaking_phase_message(self, room_id: str, message_data: dict, user_id: str) -> None:
        """
        处理发言阶段的消息 - 前端已完成验证
        """
        try:
            # 获取当前发言者
            current_speaker = await self.redis_client.zrange(f"room:{room_id}:alive_players", 0, 0)
            
            if not current_speaker or current_speaker[0] != user_id:
                # 不是当前发言者，忽略消息
                logger.warning(f"用户 {user_id} 在不是其发言轮次时尝试发言")
                return
            
            # 获取当前回合信息
            room_data = await self.redis_client.get_room_basic_data(room_id)
            current_round = room_data.get("current_round", "1")
            
            # 添加回合信息到消息数据
            message_data["round"] = current_round
            
            # 处理并广播消息 - 验证已由前端完成
            await self._handle_normal_message(room_id, message_data, user_id)
            
            # 通知游戏服务进入下一个发言者
            if self.game_service:
                await self.game_service.move_to_next_speaker(room_id)
            else:
                logger.error("无法访问game_service，无法推进发言轮次")
            
        except Exception as e:
            logger.error(f"处理发言阶段消息失败: {str(e)}")

    async def _handle_voting_phase_message(self, room_id: str, message_data: dict, user_id: str) -> None:
        """
        处理投票阶段的消息
        
        Args:
            room_id: 房间ID
            message_data: 消息数据
            user_id: 用户ID
        """
        try:
            # 获取消息内容
            content = message_data.get("content", "").strip()
            
            # 检查是否是投票命令
            if content.startswith("/vote"):
                # 尝试解析投票命令 (格式: /vote user_id)
                parts = content.split()
                if len(parts) > 1:
                    target_id = parts[1]
                    
                    # 调用GameService处理投票
                    if self.game_service:
                        # 默认投票时间为0
                        result = await self.game_service.handle_player_vote(room_id, user_id, target_id, 0.0)
                        
                        # 发送处理结果反馈
                        if result.get("success", False):
                            # 投票成功
                            system_message = f"你成功投票给了 {target_id}"
                        else:
                            # 投票失败
                            system_message = f"投票失败: {result.get('message', '未知错误')}"
                            
                        # 向投票者发送私人消息
                        await self.websocket_manager.broadcast_message(
                            invite_code=room_id,
                            message={
                                "type": "system",
                                "content": system_message,
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=True,
                            target_users={user_id}
                        )
                    else:
                        logger.error("无法访问game_service，无法处理投票")
                else:
                    # 投票命令格式错误，发送提示
                    await self.websocket_manager.broadcast_message(
                        invite_code=room_id,
                        message={
                            "type": "system",
                            "content": "投票命令格式错误，请使用 /vote user_id",
                            "timestamp": int(time.time() * 1000)
                        },
                        is_special=True,
                        target_users={user_id}
                    )
            else:
                # 非投票命令，按正常消息处理
                await self._handle_normal_message(room_id, message_data, user_id)
                
        except Exception as e:
            logger.error(f"处理投票阶段消息失败: {str(e)}")

    def set_game_service(self, game_service):
        """设置游戏服务，避免循环依赖"""
        self.game_service = game_service
        logger.info("MessageService已连接到GameService")


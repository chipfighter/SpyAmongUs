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
    - 处理websocket发送过来的消息、处理secret_channel发送的消息
    - 服务端的系统消息发送处理
    - 获取房间的消息、secret_channel消息
"""

from typing import Dict, Any, Optional, Set, List
from models.message import Message
from utils.logger_utils import get_logger
import time
import asyncio
import json
from utils.message_queue_manager import MessageQueueManager
from utils.ai_lock_manager import AILockManager
import uuid
import re

logger = get_logger(__name__)

class MessageCache:
    """
    简单的消息缓存类

    Notes:
        避免太多请求的缓存（基本都是消息历史的格式化处理缓存），需要清理掉一点，当然只能做权宜之计，如果消息量连续同时大过头就会有问题
    """
    def __init__(self, max_size=1000):
        self.cache = {}
        self.max_size = max_size
        
    def get(self, key):
        return self.cache.get(key)
        
    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            # 简单的LRU策略：删除最早的键
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = value

class MessageService:
    def __init__(self, redis_client, websocket_manager, llm_service):
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        self.llm_service = llm_service
        self.message_cache = MessageCache()
        # 每个房间的消息队列
        self.room_queues = {}
        # 每个房间的AI锁
        self.room_ai_locks = {}
        
    async def _get_room_queue(self, room_id: str):
        """获取房间的消息队列"""
        if room_id not in self.room_queues:
            self.room_queues[room_id] = asyncio.Queue()
        return self.room_queues[room_id]
        
    async def _get_room_ai_lock(self, room_id: str):
        """获取房间的AI锁"""
        if room_id not in self.room_ai_locks:
            self.room_ai_locks[room_id] = asyncio.Lock()
        return self.room_ai_locks[room_id]

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
        if msg_type is not None and msg_type not in ["chat", "secret", "system"]:
            logger.error(f"无效的消息类型: {msg_type}")
            return {
                "valid": False,
                "message": "消息类型无效"
            }
            
        # 秘密消息特殊处理
        if msg_type == "secret" and "target_users" not in message_data:
            logger.error("秘密消息缺少target_users字段")
            return {
                "valid": False,
                "message": "秘密消息必须包含target_users字段"
            }
            
        logger.info("消息格式验证通过")
        return {
            "valid": True,
            "message": "消息格式有效"
        }

    async def _stream_ai_response_to_frontend(self, room_id: str, chunk: str, is_start: bool, is_end: bool) -> None:
        """
        将AI响应流式传输到前端

        Args:
            room_id: 房间ID
            chunk: 消息内容片段
            is_start: 是否是开始
            is_end: 是否是结束
        """
        try:
            # 生成时间戳作为唯一ID
            timestamp = int(time.time() * 1000)
            
            # 构造流式消息格式 - 确保只有一个消息会话从开始到结束
            stream_message = {
                "timestamp": timestamp,
                "type": "ai_stream",    #   标识当前是什么情况的AI返回(ai_stream, secret_channel, game_chat)
                "is_start": is_start,
                "is_end": is_end,
                "content": chunk,
                "session_id": f"ai_session_{room_id}_{timestamp}" if is_start else None  # 仅在开始时创建会话ID
            }
            
            # 广播到房间
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message=stream_message,
                is_special=False  # AI流式响应不是特殊消息
            )
        except Exception as e:
            logger.error(f"流式传输AI响应失败: {str(e)}")

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
                user_name="AI助手",
                content=content
            )
            
            # 根据消息类型选择存储方式
            if is_secret:
                await self.redis_client.add_secret_channel_message(room_id, message)
            else:
                await self.redis_client.add_room_message(room_id, message)
                
        except Exception as e:
            logger.error(f"保存AI响应失败: {str(e)}")

    async def handle_ai_mention(self, room_id: str, message_data: Dict[str, Any], user_id: str) -> None:
        """处理AI提及的消息"""
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
                username = user_info.get("username", message_data.get("user_name", "Unknown"))
                
                # 广播原始消息
                await self.websocket_manager.broadcast_message(
                    room_id=room_id,
                    message={
                        "type": "chat",
                        "user_id": user_id,
                        "user_name": username,
                        "content": message_data.get("content", ""),
                        "timestamp": timestamp,
                        "is_system": False,
                        "round": "0",
                        "mentions": message_data.get("mentions", []),
                        "ai_type": message_data.get("ai_type"),
                        "room_id": room_id
                    },
                    is_special=False
                )
                logger.info("已广播用户原始消息")
            except Exception as e:
                logger.error(f"广播用户原始消息失败: {str(e)}")
            
            # 获取聊天历史
            chat_history_dicts = await self.get_room_messages(room_id)
            
            # 将字典转换为Message对象
            chat_history = []
            for msg_dict in chat_history_dicts:
                try:
                    message = Message(
                        timestamp=msg_dict.get("timestamp", int(time.time() * 1000)),
                        user_id=msg_dict.get("user_id", ""),
                        user_name=msg_dict.get("username", "Unknown"),
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
            
            # 调用LLM处理消息
            async for chunk in self.llm_service.chat_completion(
                messages=chat_history,
                current_message=message_data.get("content", ""),
                context_type="normal_chat"  # 默认使用普通聊天场景
            ):
                # 累积完整响应
                full_ai_response += chunk
                
                # 处理当前块，防止显示多余的空行
                processed_chunk = re.sub(r'\n{3,}', '\n\n', chunk)
                
                # 构造流式消息
                chunk_timestamp = int(time.time() * 1000)
                stream_message = {
                    "timestamp": chunk_timestamp,
                    "type": "ai_stream",
                    "is_start": is_first_chunk,
                    "is_end": False,
                    "content": processed_chunk,
                    "session_id": session_id  # 使用会话ID保持消息关联
                }
                
                # 广播到房间
                await self.websocket_manager.broadcast_message(
                    room_id=room_id,
                    message=stream_message,
                    is_special=False
                )
                
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
            
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message=end_message,
                is_special=False
            )
            
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
            
            # 2. 处理AI响应（去除多余的空行）并存储
            # 将3个或更多连续换行符替换为2个
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
            
        except Exception as e:
            logger.error(f"处理AI消息失败: {str(e)}")
            # 发送错误消息到前端
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message={
                    "type": "error",
                    "message": f"AI处理失败: {str(e)}",
                    "timestamp": int(time.time() * 1000)
                },
                is_special=False  # 错误消息不是特殊消息
            )

    async def process_message(self, message_data: dict) -> dict:
        """处理消息"""
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
            
            logger.info(f"获取房间 {room_id} 的消息队列")
            queue = await self._get_room_queue(room_id)
            
            logger.info(f"将消息放入队列: {message_data}")
            await queue.put(message_data)
            
            logger.info("创建异步处理任务")
            asyncio.create_task(self._process_queued_message(room_id, user_id))
            
            return {"success": True, "message": "Message queued successfully"}
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            return {"success": False, "message": f"Failed to process message: {str(e)}"}
            
    async def _process_queued_message(self, room_id: str, user_id: str):
        """处理消息队列中的消息"""
        try:
            logger.info(f"开始处理房间 {room_id} 队列中的消息")
            queue = await self._get_room_queue(room_id)
            message_data = await queue.get()
            logger.info(f"从队列获取消息: {message_data}")
            
            # 检查是否是AI消息
            contains_ai_mention = False
            if "mentions" in message_data:
                logger.info(f"检查mentions字段: {message_data['mentions']}")
                # 检查mentions数组中是否有ai_assistant
                contains_ai_mention = any(mention.get('id') == 'ai_assistant' for mention in message_data["mentions"])
            
            if contains_ai_mention or message_data.get('ai_type'):
                logger.info("检测到AI提及，准备获取AI锁")
                # 获取AI锁
                ai_lock = await self._get_room_ai_lock(room_id)
                logger.info("获取AI锁成功，准备处理AI提及消息")
                async with ai_lock:
                    await self.handle_ai_mention(room_id, message_data, user_id)
            else:
                # 普通消息直接处理
                logger.info("检测到普通消息，直接处理")
                await self._handle_normal_message(room_id, message_data, user_id)
                
        except Exception as e:
            logger.error(f"处理队列消息失败: {str(e)}")
            
    async def _handle_normal_message(self, room_id: str, message_data: dict, user_id: str):
        """处理普通消息"""
        try:
            logger.info(f"处理普通消息: {message_data}")
            content = message_data.get("content")
            
            # 获取用户信息
            user_info = await self.redis_client.hgetall(f"user:{user_id}")
            logger.info(f"获取到用户信息: {user_info}")
            username = user_info.get("username", message_data.get("user_name", "Unknown"))
            
            # 创建消息对象
            message = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "user_name": username,  # 使用user_name而不是username
                "content": content,
                "timestamp": int(time.time() * 1000),  # 使用毫秒时间戳

            }

            logger.info(f"创建消息对象: {message}")

            # 使用pipeline存储消息
            pipe = await self.redis_client.pipeline()
            pipe.lpush(f"room:{room_id}:messages", json.dumps(message))
            pipe.expire(f"room:{room_id}:messages", 24 * 60 * 60)
            logger.info("执行Redis pipeline")
            await pipe.execute()

            # 广播消息到房间
            logger.info(f"广播消息到房间 {room_id}")
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message={
                    "type": "chat",  # 明确指定消息类型
                    "user_id": user_id,
                    "user_name": username,  # 使用user_name而不是username
                    "content": content,
                    "timestamp": int(time.time() * 1000),
                },
                is_special=False  # 普通消息不是特殊消息
            )
            logger.info("消息广播成功")
            
        except Exception as e:
            logger.error(f"处理普通消息失败: {str(e)}")
            # 尝试发送错误消息到前端
            try:
                await self.websocket_manager.broadcast_message(
                    room_id=room_id,
                    message={
                        "type": "error",  # 明确指定错误消息类型
                        "message": f"处理消息失败: {str(e)}",
                        "timestamp": int(time.time() * 1000)
                    },
                    is_special=False  # 错误消息也不是特殊消息
                )
            except Exception as broadcast_error:
                logger.error(f"发送错误消息失败: {str(broadcast_error)}")

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
            user_name = user_data.get("username", "未知用户")
            content = message_data.get("content", "")
            
            message = Message.create_user_message(
                user_id=user_id,
                user_name=user_name,
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
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message={**message_dict, "type": "secret"},  # 添加类型标识
                is_special=True,
                target_users=set(target_users)
            )
            
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
            
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message=message_dict,
                is_special=False,   # 默认广播全部用户
                target_users=target_users
            )
            
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
            # 这里需要根据具体实现来确定如何过滤
            # 暂时以用户ID作为筛选条件，实际可能需要根据target_users等字段判断
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


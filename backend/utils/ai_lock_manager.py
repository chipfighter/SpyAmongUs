"""
utils: ai_lock_manager

Description:
    管理房间级别的AI处理锁

Notes:
    具体场景是正常对话的时候问完AI以后，需要等待llm server的回应，所以需要等待一段时间，但是为了保持消息存储的时序性，所以保留AI锁机制
"""

import json
from utils.logger_utils import get_logger

logger = get_logger(__name__)


class AIStorageLockManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    async def acquire_storage_lock(self, room_id: str, timeout: int = 65) -> bool:
        """
        获取房间的消息存储锁（用于AI流式响应期间）

        Args:
            room_id: 房间ID
            timeout: 锁超时时间（秒）- 设为LLM超时+5秒余量

        Returns:
            bool: 是否成功获取锁
        """
        lock_key = f"room:{room_id}:storage_lock"
        
        # 使用Redis的setnx命令模拟实现锁
        # 先检查键是否存在
        exists = await self.redis_client.exists(lock_key) > 0
        if exists:
            logger.info(f"房间 {room_id} 的存储锁已被占用")
            return False
        
        # 设置锁并设置过期时间
        await self.redis_client.set(lock_key, "1")
        await self.redis_client.expire(lock_key, timeout)
        
        logger.info(f"成功获取房间 {room_id} 的存储锁")
        return True

    async def release_storage_lock(self, room_id: str) -> None:
        """
        释放房间的消息存储锁

        Args:
            room_id: 房间ID
        """
        lock_key = f"room:{room_id}:storage_lock"
        await self.redis_client.delete(lock_key)
        logger.info(f"已释放房间 {room_id} 的存储锁")

    async def is_storage_locked(self, room_id: str) -> bool:
        """
        检查房间的消息存储是否被锁定

        Args:
            room_id: 房间ID

        Returns:
            bool: 是否被锁定
        """
        lock_key = f"room:{room_id}:storage_lock"
        result = await self.redis_client.exists(lock_key) > 0
        return result

    async def add_pending_message(self, room_id: str, message: dict) -> None:
        """
        添加消息到待处理队列（在AI处理期间）

        Args:
            room_id: 房间ID
            message: 消息数据
        """
        queue_key = f"room:{room_id}:pending_messages"
        await self.redis_client.rpush(queue_key, json.dumps(message))
        # 设置相同的过期时间
        await self.redis_client.expire(queue_key, 65)
        logger.info(f"已将消息添加到房间 {room_id} 的待处理队列")

    async def get_pending_messages(self, room_id: str) -> list:
        """
        获取所有待处理消息

        Args:
            room_id: 房间ID

        Returns:
            list: 待处理消息列表
        """
        queue_key = f"room:{room_id}:pending_messages"
        messages = await self.redis_client.lrange(queue_key, 0, -1)
        parsed_messages = [json.loads(msg) for msg in messages]
        logger.info(f"从房间 {room_id} 的待处理队列获取了 {len(parsed_messages)} 条消息")
        return parsed_messages

    async def clear_pending_messages(self, room_id: str) -> None:
        """
        清空待处理消息队列

        Args:
            room_id: 房间ID
        """
        queue_key = f"room:{room_id}:pending_messages"
        await self.redis_client.delete(queue_key)
        logger.info(f"已清空房间 {room_id} 的待处理消息队列")

    async def process_pending_messages(self, room_id: str, processor_func) -> None:
        """
        处理所有待处理的消息

        Args:
            room_id: 房间ID
            processor_func: 处理消息的函数（接收一个消息参数的异步函数）
        """
        try:
            # 获取所有待处理消息
            pending_messages = await self.get_pending_messages(room_id)

            if not pending_messages:
                logger.info(f"房间 {room_id} 没有待处理消息")
                return

            logger.info(f"开始处理房间 {room_id} 的 {len(pending_messages)} 条待处理消息")

            # 逐个处理消息
            for message in pending_messages:
                try:
                    await processor_func(message)
                except Exception as e:
                    logger.error(f"处理待处理消息时出错: {str(e)}")

            # 清空待处理队列
            await self.clear_pending_messages(room_id)

        except Exception as e:
            logger.error(f"处理待处理消息队列时出错: {str(e)}")
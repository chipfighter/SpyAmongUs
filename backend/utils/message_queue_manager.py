"""
utils: message_queue_manager

Description:
    管理房间级别的消息队列
"""

import json
import asyncio
from typing import Dict, Any, Optional
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class MessageQueueManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.queue_tasks = {}  # 存储每个房间的队列处理任务
        
    async def add_message(self, room_id: str, message_data: Dict[str, Any]) -> None:
        """
        将消息添加到房间的消息队列
        
        Args:
            room_id: 房间ID
            message_data: 消息数据
        """
        queue_key = f"room:{room_id}:message_queue"
        await self.redis_client.rpush(queue_key, json.dumps(message_data))
        logger.info(f"消息已添加到房间 {room_id} 的消息队列")
        
    async def get_next_message(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        从房间的消息队列获取下一条消息
        
        Args:
            room_id: 房间ID
            
        Returns:
            Optional[Dict[str, Any]]: 消息数据，如果队列为空则返回None
        """
        queue_key = f"room:{room_id}:message_queue"
        message_json = await self.redis_client.lpop(queue_key)
        if message_json:
            return json.loads(message_json)
        return None
        
    async def start_queue_processor(self, room_id: str, message_handler) -> None:
        """
        启动房间的消息队列处理任务
        
        Args:
            room_id: 房间ID
            message_handler: 消息处理函数
        """
        if room_id not in self.queue_tasks:
            self.queue_tasks[room_id] = asyncio.create_task(
                self._process_queue(room_id, message_handler)
            )
            logger.info(f"已启动房间 {room_id} 的消息队列处理任务")
            
    async def _process_queue(self, room_id: str, message_handler) -> None:
        """
        处理房间的消息队列
        
        Args:
            room_id: 房间ID
            message_handler: 消息处理函数
        """
        try:
            while True:
                # 获取下一条消息
                message_data = await self.get_next_message(room_id)
                if not message_data:
                    # 队列为空，停止处理
                    if room_id in self.queue_tasks:
                        self.queue_tasks[room_id].cancel()
                        del self.queue_tasks[room_id]
                    return
                    
                # 处理消息
                await message_handler(room_id, message_data)
                
        except Exception as e:
            logger.error(f"处理消息队列出错: {str(e)}")
            if room_id in self.queue_tasks:
                self.queue_tasks[room_id].cancel()
                del self.queue_tasks[room_id]
                
    def stop_queue_processor(self, room_id: str) -> None:
        """
        停止房间的消息队列处理任务
        
        Args:
            room_id: 房间ID
        """
        if room_id in self.queue_tasks:
            self.queue_tasks[room_id].cancel()
            del self.queue_tasks[room_id]
            logger.info(f"已停止房间 {room_id} 的消息队列处理任务") 
"""
message_service

Notes:

"""

from typing import Dict, List, Any, Set
import asyncio
from utils.redis_utils import RedisClient
from models.message import Message
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class MessageService:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        # 使用Set存储连接，提高查找效率
        self.room_connections: Dict[str, Set[Any]] = {}
        # 消息广播锁，防止并发问题
        self._broadcast_locks: Dict[str, asyncio.Lock] = {}

    async def save_message(self, room_id: str, message: Dict) -> None:
        """保存消息到Redis"""
        await self.redis.save_message(room_id, message)

    async def get_message_history(self, room_id: str, limit: int = 50) -> List[Dict]:
        """获取房间的历史消息"""
        return await self.redis.get_messages(room_id, limit)

    async def broadcast_message(self, room_id: str, message: Dict) -> None:
        """广播消息到房间内的所有连接"""
        # 获取或创建房间的广播锁
        if room_id not in self._broadcast_locks:
            self._broadcast_locks[room_id] = asyncio.Lock()

        async with self._broadcast_locks[room_id]:
            # 保存消息
            try:
                await self.save_message(room_id, message)
            except Exception as e:
                logger.error(f"保存消息到Redis失败: {e}")

            # 获取房间的所有连接
            connections = self.get_room_connections(room_id)
            if not connections:
                return

            # 创建发送任务列表
            tasks = []
            for connection in connections:
                task = asyncio.create_task(
                    self._send_message(connection, message)
                )
                tasks.append(task)

            # 并发发送消息
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_message(self, connection: Any, message: Dict) -> None:
        """发送单条消息，处理异常"""
        try:
            # 打印一下当前要发送的消息，方便调试
            logger.debug(f"即将发送消息: {message}")
            
            await connection.send_json({
                "type": "message",
                "data": message  # 将消息内容放在data字段下
            })
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            # 如果发送失败，从连接列表中移除
            for room_id, connections in self.room_connections.items():
                if connection in connections:
                    connections.remove(connection)
                    if not connections:
                        del self.room_connections[room_id]
                    break

    async def broadcast_system_message(self, room_id: str, content: str) -> None:
        """广播系统消息"""
        system_message = Message.create_system_message(room_id, content)
        
        # 获取或创建房间的广播锁
        if room_id not in self._broadcast_locks:
            self._broadcast_locks[room_id] = asyncio.Lock()

        async with self._broadcast_locks[room_id]:
            # 保存消息到Redis
            try:
                await self.save_message(room_id, system_message.dict())
            except Exception as e:
                logger.error(f"保存系统消息到Redis失败: {e}")

            # 获取房间的所有连接
            connections = self.get_room_connections(room_id)
            if not connections:
                return

            # 创建发送任务列表
            tasks = []
            for connection in connections:
                task = asyncio.create_task(
                    connection.send_json({
                        "type": "system_message",
                        "data": system_message.dict()
                    })
                )
                tasks.append(task)

            # 并发发送消息
            await asyncio.gather(*tasks, return_exceptions=True)

    def register_connection(self, room_id: str, connection: Any) -> None:
        """注册房间的WebSocket连接"""
        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(connection)

    def unregister_connection(self, room_id: str, connection: Any) -> None:
        """取消注册房间的WebSocket连接"""
        if room_id in self.room_connections and connection in self.room_connections[room_id]:
            self.room_connections[room_id].remove(connection)
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
                # 清理广播锁
                if room_id in self._broadcast_locks:
                    del self._broadcast_locks[room_id]

    def get_room_connections(self, room_id: str) -> List[Any]:
        """获取房间的所有连接"""
        return list(self.room_connections.get(room_id, set()))
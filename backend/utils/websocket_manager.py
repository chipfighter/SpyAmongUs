"""
utils: websocket_manager

Description:
    管理每个用户-房间的websocket连接

Notes:
    - 建立连接、从房间中移除对应用户连接
    - 广播消息到房间内对应用户
    - 关闭房间内所有连接
"""
import json
from fastapi import WebSocket
from typing import Dict, Set, Optional, Any
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    def __init__(self):
        # 房间连接池
        self.room_connections = {}  # room_id -> {user_id -> connection}

    async def add_connection(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        """添加新连接到房间"""
        if room_id not in self.room_connections:
            self.room_connections[room_id] = {}
        self.room_connections[room_id][user_id] = websocket
        logger.debug(f"用户 {user_id} 已连接到房间 {room_id}")

    async def remove_user_connection(self, room_id: str, user_id: str) -> None:
        """从房间移除对应用户的连接"""
        if room_id in self.room_connections and user_id in self.room_connections[room_id]:
            del self.room_connections[room_id][user_id]
            logger.debug(f"用户 {user_id} 已从房间 {room_id} 断开连接")
            # 如果房间没有连接了，清理房间
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
                logger.debug(f"房间 {room_id} 已没有连接，移除房间")

    async def close_room_connections(self, room_id: str, users: list) -> None:
        """
        关闭房间内所有WebSocket连接

        Args:
            room_id: 房间ID
            users: 房间内的用户ID列表（从Redis获取，在service中调用的时候传入）
        """
        if not users:
            logger.warning(f"尝试关闭空房间的连接: {room_id}")
            return

        logger.info(f"关闭房间 {room_id} 的所有连接，用户数: {len(users)}")
        disconnected_users = []

        # 遍历Redis中的用户列表
        for user_id in users:
            # 检查用户是否有WebSocket连接
            if room_id in self.room_connections and user_id in self.room_connections[room_id]:
                websocket = self.room_connections[room_id][user_id]
                try:
                    await websocket.close(code=1000, reason="房间已关闭")
                    disconnected_users.append(user_id)
                except Exception as e:
                    logger.error(f"关闭用户 {user_id} 连接失败: {str(e)}")
                    disconnected_users.append(user_id)

        # 清理所有连接
        for user_id in disconnected_users:
            await self.remove_user_connection(room_id, user_id)

        # 如果房间仍在连接池中，移除它
        if room_id in self.room_connections:
            del self.room_connections[room_id]

        logger.info(f"房间 {room_id} 的所有连接已关闭，实际关闭连接数: {len(disconnected_users)}")
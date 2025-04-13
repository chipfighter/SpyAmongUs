"""
utils: websocket_manager

Description:
    管理每个用户-房间的websocket连接

Notes:
    仅仅负责和websocket直接相关的操作，关于消息的处理和房间的管理完全隔离开
    - 建立连接、从房间中移除对应用户连接
    - 关闭房间内所有连接
    - 广播消息（到对应用户）
"""
import json
import asyncio  # 添加asyncio导入
from fastapi import WebSocket
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    def __init__(self):
        # 嵌套字典来保存连接 room_id -> {user_id -> connection}
        self.room_connections = {}

    async def add_connection(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        """添加新连接到房间"""
        if room_id not in self.room_connections:
            self.room_connections[room_id] = {}
        self.room_connections[room_id][user_id] = websocket
        logger.info(f"用户 {user_id} 已连接到房间 {room_id}")

    async def remove_user_connection(self, room_id: str, user_id: str) -> None:
        """从房间移除对应用户的连接"""
        if room_id in self.room_connections and user_id in self.room_connections[room_id]:
            del self.room_connections[room_id][user_id]
            logger.info(f"用户 {user_id} 已从房间 {room_id} 断开连接")
            # 如果房间没有连接了，清理房间
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
                logger.info(f"房间 {room_id} 已没有连接，移除房间")

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

    async def broadcast_message(self, room_id: str, message: dict, is_special: bool, target_users: set = None) -> None:
        """
        广播消息到房间

        Args:
            room_id: 房间ID
            message: 消息内容
            is_special: 消息是否特殊呢（secret_channel或其他情况）
            target_users: 目标用户集合

        Notes:
            提供给message_service来判断转发
        """
        if room_id not in self.room_connections:
            return

        # 序列化消息
        message_text = json.dumps(message)

        # 确定目标用户
        if is_special:
            # 广播给指定用户集合
            targets = [user_id for user_id in target_users
                       if user_id in self.room_connections[room_id]]
        else:
            # 广播给所有用户
            targets = self.room_connections[room_id].keys()

        # 准备所有发送任务
        send_tasks = []
        for user_id in targets:
            websocket = self.room_connections[room_id].get(user_id)
            if websocket:
                # 将每个发送操作添加到任务列表，而不是直接等待
                send_tasks.append(self._send_message_to_user(
                    room_id, user_id, websocket, message_text))

        # 并行执行所有发送任务
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
            
    async def _send_message_to_user(self, room_id: str, user_id: str, websocket: WebSocket, message_text: str) -> None:
        """
        向单个用户发送消息
        
        Args:
            room_id: 房间ID
            user_id: 用户ID
            websocket: WebSocket连接
            message_text: 序列化后的消息文本
            
        Notes:
            辅助方法，用于在broadcast_message中支持并行发送
        """
        try:
            await websocket.send_text(message_text)
        except Exception as e:
            logger.error(f"向用户 {user_id} 发送消息失败: {str(e)}")
            # 尝试判断连接是否已断开
            try:
                # 发送简单的ping消息测试连接
                await websocket.send_json({"type": "ping_test"})
            except Exception:
                logger.warning(f"确认用户 {user_id} 连接已断开，从房间 {room_id} 移除连接")
                # 如果无法发送，说明连接确实断开，移除连接
                await self.remove_user_connection(room_id, user_id)
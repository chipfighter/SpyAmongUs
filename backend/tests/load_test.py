"""
用于简单的压力测试模拟，
"""

import asyncio
import websockets
import json
import random
import time
from datetime import datetime
from typing import List, Dict
import uuid

# 将相对路径添加到模块搜索路径
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.logger_utils import setup_logger, get_logger

# 配置日志
setup_logger("LoadTest")
logger = get_logger(__name__)


class LoadTest:
    def __init__(self, server_url: str = "ws://localhost:8000"):
        self.server_url = server_url
        self.connections: Dict[str, websockets.WebSocketClientProtocol] = {}
        self.rooms: List[str] = []
        self.test_start_time = None
        self.test_end_time = None
        self.messages_sent = 0
        self.messages_received = 0

    async def create_user(self, user_id: str = None) -> str:
        """创建测试用户"""
        if not user_id:
            user_id = str(uuid.uuid4())

        try:
            ws = await websockets.connect(f"{self.server_url}/ws/{user_id}")
            self.connections[user_id] = ws
            logger.info(f"User {user_id} connected")
            return user_id
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return None

    async def create_room(self, user_id: str) -> str:
        """创建房间"""
        try:
            ws = self.connections[user_id]
            room_name = f"Test Room {random.randint(1000, 9999)}"

            await ws.send(json.dumps({
                "type": "create_room",
                "data": {
                    "name": room_name,
                    "is_public": True,
                    "username": f"User_{user_id[:8]}"
                }
            }))

            response = await ws.recv()
            data = json.loads(response)

            if data["type"] == "room_created":
                room_id = data["data"]["id"]
                self.rooms.append(room_id)
                logger.info(f"Room {room_id} created by user {user_id}")
                return room_id
            else:
                logger.error(f"Failed to create room: {data}")
                return None
        except Exception as e:
            logger.error(f"Error creating room: {e}")
            return None

    async def send_message(self, user_id: str, room_id: str, content: str):
        """发送消息"""
        try:
            ws = self.connections[user_id]
            await ws.send(json.dumps({
                "type": "message",
                "data": {
                    "room_id": room_id,
                    "content": content,
                    "username": f"User_{user_id[:8]}"
                }
            }))
            self.messages_sent += 1
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def run_test(self, num_users: int = 10, messages_per_user: int = 100):
        """运行压力测试"""
        self.test_start_time = datetime.now()
        logger.info(f"Starting load test with {num_users} users and {messages_per_user} messages per user")

        # 创建用户
        users = []
        for i in range(num_users):
            user_id = await self.create_user()
            if user_id:
                users.append(user_id)

        # 创建房间
        rooms = []
        for user_id in users:
            room_id = await self.create_room(user_id)
            if room_id:
                rooms.append(room_id)

        # 发送消息
        tasks = []
        for user_id in users:
            for _ in range(messages_per_user):
                room_id = random.choice(rooms)
                content = f"Test message {random.randint(1, 1000)}"
                task = asyncio.create_task(
                    self.send_message(user_id, room_id, content)
                )
                tasks.append(task)
                # 添加小延迟避免消息过于密集
                await asyncio.sleep(0.01)

        # 等待所有消息发送完成
        await asyncio.gather(*tasks)

        self.test_end_time = datetime.now()

        # 输出测试结果
        duration = (self.test_end_time - self.test_start_time).total_seconds()
        logger.info(f"Load test completed in {duration:.2f} seconds")
        logger.info(f"Total messages sent: {self.messages_sent}")
        logger.info(f"Messages per second: {self.messages_sent / duration:.2f}")

        # 关闭所有连接
        for ws in self.connections.values():
            await ws.close()


async def main():
    # 测试参数
    num_users = 20  # 并发用户数
    messages_per_user = 200  # 每个用户发送的消息数

    load_test = LoadTest()
    await load_test.run_test(num_users, messages_per_user)


if __name__ == "__main__":
    asyncio.run(main())
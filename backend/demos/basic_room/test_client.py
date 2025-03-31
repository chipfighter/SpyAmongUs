"""basic_room的测试文件（有点鸡肋）"""

import asyncio
import websockets
import json
import requests
import time
import random
import sys


async def send_messages(uri, name):
    """模拟客户端发送消息"""
    async with websockets.connect(uri) as websocket:
        # 首先发送用户名
        await websocket.send(json.dumps({"name": name}))

        # 等待连接确认
        response = await websocket.recv()
        print(f"[{name}] 收到: {response}")

        # 发送消息线程
        async def sender():
            messages = [
                f"{name}的测试消息-1",
                f"{name}的测试消息-2",
                f"大家好，我是{name}",
                f"{name}在测试聊天功能"
            ]

            for message in messages:
                await asyncio.sleep(random.uniform(1, 3))  # 随机延迟
                msg = json.dumps({"content": message})
                await websocket.send(msg)
                print(f"[{name}] 发送: {message}")

        # 接收消息线程
        async def receiver():
            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)

                    if data["type"] == "message":
                        print(f"[{data['timestamp']}] {data['user_name']}: {data['content']}")
                    elif data["type"] == "system":
                        print(f"[系统消息] {data['message']}")
                except Exception as e:
                    print(f"接收失败: {e}")
                    break

        # 运行发送和接收任务
        sender_task = asyncio.create_task(sender())
        receiver_task = asyncio.create_task(receiver())

        # 等待发送任务完成，但保持接收任务运行
        await sender_task

        # 保持连接一段时间以接收消息
        await asyncio.sleep(10)

        # 取消接收任务
        receiver_task.cancel()


def create_or_join_room():
    """创建房间或获取现有房间"""
    try:
        # 获取房间列表
        response = requests.get("http://localhost:8000/api/rooms")
        rooms = response.json()

        # 如果有未满的房间，加入第一个
        for room in rooms:
            if not room["is_full"]:
                return room["room_id"]

        # 否则创建新房间
        response = requests.post("http://localhost:8000/api/rooms")
        return response.json()["room_id"]
    except Exception as e:
        print(f"获取房间失败: {e}")
        return None


async def main():
    # 获取用户输入的名称或使用默认值
    name = sys.argv[1] if len(sys.argv) > 1 else f"测试用户-{random.randint(1, 100)}"

    # 获取或创建房间
    room_id = create_or_join_room()
    if not room_id:
        print("无法获取房间，测试结束")
        return

    print(f"加入房间: {room_id}, 用户名: {name}")

    # 连接到websocket
    uri = f"ws://localhost:8000/ws/{room_id}"
    await send_messages(uri, name)


if __name__ == "__main__":
    asyncio.run(main())
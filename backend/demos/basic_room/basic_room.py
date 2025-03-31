from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Set
import json
import uuid
from datetime import datetime
import uvicorn

app = FastAPI()

# 允许的来源列表（白名单）
allowed_origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:5173",  # Vite 默认端口
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]
# 添加CORS中间件，允许跨域前端连接
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # 允许的来源
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # 限制的方法
    allow_headers=["*"],
)


# 房间信息表示（之后换class，这里仅仅简单解析）
rooms: Dict[str, Dict] = {}  # room_id -> {users: {user_id: {ws, name}}, messages: []}
MAX_ROOM_SIZE = 4  # 房间最大人数限制


# 创建房间API
@app.post("/api/rooms")
async def create_room():
    room_id = str(uuid.uuid4())[:8]  # 使用32位uuid（前8个字符）来简单测试
    rooms[room_id] = {"users": {}, "messages": []}  # room信息初始化
    return {"room_id": room_id}


# 房间列表API
@app.get("/api/rooms")
async def list_rooms():
    result = []
    for room_id, room_data in rooms.items():
        result.append({
            "room_id": room_id,
            "user_count": len(room_data["users"]),
            "is_full": len(room_data["users"]) >= MAX_ROOM_SIZE
        })
    return result


# WebSocket聊天室连接
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()    # 接收客户端的WebSocket连接

    user_id = None  # 初始化用户id

    try:
        # 等待用户发送名称
        first_message = await websocket.receive_text()  # 等待第一个消息
        user_data = json.loads(first_message)   # 解析JSON
        user_name = user_data.get("name", f"用户_{str(uuid.uuid4())[:4]}")
        user_id = str(uuid.uuid4())

        # 检查房间是否存在
        if room_id not in rooms:
            rooms[room_id] = {"users": {}, "messages": []}

        # 检查房间是否已满
        if len(rooms[room_id]["users"]) >= MAX_ROOM_SIZE:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "房间已满"
            }))
            await websocket.close()
            return

        # 用户加入房间
        rooms[room_id]["users"][user_id] = {"ws": websocket, "name": user_name}

        # 发送用户ID给客户端
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user_id": user_id
        }))

        # 通知房间内所有人有新用户加入
        join_message = {
            "type": "system",
            "message": f"{user_name} 加入了聊天室",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        await broadcast_message(room_id, join_message)

        # 发送历史消息给新用户
        for message in rooms[room_id]["messages"]:
            await websocket.send_text(json.dumps(message))

        # 消息处理循环
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # 构建消息
            message = {
                "type": "message",
                "user_id": user_id,
                "user_name": user_name,
                "content": message_data.get("content", ""),
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }

            # 保存消息
            if len(rooms[room_id]["messages"]) > 100:  # 限制消息历史
                rooms[room_id]["messages"] = rooms[room_id]["messages"][-100:]
            rooms[room_id]["messages"].append(message)

            # 广播消息
            await broadcast_message(room_id, message)

    except WebSocketDisconnect:
        # 用户离开处理
        if user_id and room_id in rooms and user_id in rooms[room_id]["users"]:
            user_name = rooms[room_id]["users"][user_id]["name"]
            del rooms[room_id]["users"][user_id]

            # 通知其他用户
            leave_message = {
                "type": "system",
                "message": f"{user_name} 离开了聊天室",
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
            await broadcast_message(room_id, leave_message)

            # 如果房间空了，清理房间
            if len(rooms[room_id]["users"]) == 0:
                del rooms[room_id]
    except Exception as e:
        print(f"Error: {e}")
        if user_id and room_id in rooms and user_id in rooms[room_id]["users"]:
            del rooms[room_id]["users"][user_id]
            if len(rooms[room_id]["users"]) == 0:
                del rooms[room_id]


async def broadcast_message(room_id, message):
    """向房间内所有用户广播消息"""
    if room_id in rooms:
        for user_id, user_data in rooms[room_id]["users"].items():
            try:
                await user_data["ws"].send_text(json.dumps(message))
            except:
                # 如果发送失败，可能是连接已断开
                pass


if __name__ == "__main__":
    print("正在启动聊天室服务器...")
    print("服务器地址: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
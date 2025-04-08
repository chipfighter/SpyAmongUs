"""
核心文件：多人聊天系统v0.0.3
"""

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
import traceback
import json
import os

from models.message import Message
from services.room_service import RoomService
from services.user_service import UserService
from services.message_service import MessageService
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.logger_utils import setup_logger, get_logger
from config import APP_HOST, APP_PORT, DEBUG

# 配置日志
setup_logger("SpyAmongUs")
logger = get_logger(__name__)

# WebSocket连接管理（监听所有与服务器端的connection）
class ConnectionManager:
    def __init__(self):
        # 存储所有活跃的WebSocket连接
        self.active_connections = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"用户 {user_id} 连接成功")
    
    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"用户 {user_id} 断开连接")
    
    async def send_json(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
            
    def disconnect_all(self):
        """断开所有连接"""
        self.active_connections = {}
        logger.info("所有WebSocket连接已断开")

app = FastAPI(title="SpyAmongUs Chat API")

# CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # 当前测试用的是不限制，注意之后的代码修改！！！
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 初始化服务
redis_client = RedisClient()
mongo_client = MongoClient()
connection_manager = ConnectionManager()
user_service = None
room_service = None
message_service = None


@app.on_event("startup")
async def startup_event():
    """启动时运行的初始化代码"""
    global user_service, room_service, message_service
    
    logger.info("应用启动，开始初始化...")
    
    # 创建数据目录
    os.makedirs("data", exist_ok=True)
    
    try:
        # 连接Redis（调用redis_utils）
        logger.info("正在连接Redis...")
        await redis_client.connect()
        
        # 连接MongoDB（调用mongo_utils）
        logger.info("正在连接MongoDB...")
        await mongo_client.connect()
        
        # 初始化服务
        logger.info("正在初始化服务...")
        user_service = UserService(redis_client, mongo_client)
        room_service = RoomService(redis_client)
        message_service = MessageService(redis_client)
        
        # 启动后台任务
        logger.info("正在启动后台任务...")
        await room_service.start_background_tasks()
        
        logger.info("应用初始化完成，准备接受请求")
    except Exception as e:
        logger.error(f"应用初始化失败: {str(e)}")
        raise
        
@app.on_event("shutdown")
async def shutdown_event():
    """关闭时运行的清理代码"""
    logger.info("应用关闭，开始清理资源...")
    
    # 停止后台任务
    if room_service:
        await room_service.stop_background_tasks()
    
    # 关闭redis、mongodb、所有websocket连接
    await redis_client.disconnect()
    await mongo_client.disconnect()
    connection_manager.disconnect_all()
    
    logger.info("资源清理完成，应用已安全关闭")


# 用户API - 登录
@app.post("/api/login")
async def login(
    username: str = Body(...), 
    password: str = Body(...)
):
    """用户名密码登录"""
    try:
        # 确保用户服务已初始化
        if not user_service:
            raise HTTPException(status_code=500, detail="用户服务未初始化")
        
        # 登录用户
        success, user, message = await user_service.login_with_password(username, password)
        
        if not success:
            raise HTTPException(status_code=401, detail=message)
        
        # 设置用户为在线状态
        await user_service.set_user_online(user.id)
        
        # 返回用户信息
        return {
            "success": True,
            "message": message,
            "user": user.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


# 用户API - 注册
@app.post("/api/register")
async def register(
    username: str = Body(...), 
    password: str = Body(...)
):
    """用户注册"""
    # 验证输入
    if not username or len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名太短")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="密码太短，至少需要6个字符")
    
    try:
        # 确保用户服务已初始化
        if not user_service:
            raise HTTPException(status_code=500, detail="用户服务未初始化")
        
        # 创建用户
        success, user, message = await user_service.create_user(username, password)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # 返回用户信息
        return {
            "success": True,
            "message": message,
            "user": user.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


# 处理所有websocket请求（统一入口）
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """处理WebSocket连接和消息通信。

    实现实时双向通信功能，包括用户连接管理、消息路由与分发、房间操作和聊天功能。

    支持的消息类型:
        - create_room: 创建新房间
        - join_room: 加入已有房间
        - message: 发送聊天消息
        - leave_room: 离开当前房间
        - get_public_rooms: 获取公开房间列表

    Args:
        websocket: FastAPI提供的WebSocket对象

    Raises:
        WebSocketDisconnect: 当客户端断开连接时
        Exception: 处理消息过程中遇到的其他异常
    """
    user_id = websocket.query_params.get("user_id")
    if not user_id:
        await websocket.close(code=1008, reason="没有提供用户ID")
        return
        
    try:
        # 接受WebSocket连接
        await connection_manager.connect(user_id, websocket)
        
        # 设置用户为在线状态
        await user_service.set_user_online(user_id)
        
        # 初始响应
        await websocket.send_json({
            "type": "connection_established",
            "message": "WebSocket连接成功",
            "user_id": user_id
        })
        
        # 如果Redis未连接，先尝试连接（这部分主要给前端测试看的，之后stable version可以删掉）
        if redis_client._redis is None:
            logger.info("Redis未连接，尝试连接...")
            try:
                await redis_client.connect()
                logger.info("Redis连接成功")
            except Exception as e:
                logger.error(f"Redis连接失败: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "error": "服务器错误",
                    "details": "Redis连接失败，请稍后重试",
                    "action": "connect"
                })
        
        while True:
            # 等待接收消息
            data_raw = await websocket.receive_text()
            
            try:
                data = json.loads(data_raw)
                message_type = data.get('type', '')
                logger.info(f"收到消息类型: {message_type}, 用户ID: {user_id}")
                
                # 检查Redis连接
                if redis_client._redis is None:
                    error_msg = "Redis连接失败"
                    logger.error(f"错误: {error_msg}")
                    
                    # 尝试重新连接Redis
                    logger.info("尝试重新连接Redis...")
                    await redis_client.connect()
                    
                    if redis_client._redis is None:
                        await websocket.send_json({
                            "type": "error",
                            "error": error_msg,
                            "details": "无法连接到Redis服务器",
                            "action": "create_room" if message_type == "create_room" else message_type
                        })
                        continue
                    else:
                        logger.info("Redis重新连接成功")
            
                # 处理不同类型的消息
                if message_type == "create_room":
                    # 1.创建房间
                    try:
                        # 验证必须字段
                        if 'room_name' not in data:
                            raise ValueError("缺少房间名称")
                        if 'user_id' not in data:
                            raise ValueError("缺少用户ID")
                        if 'username' not in data:
                            raise ValueError("缺少用户名")
                        
                        room_name = data['room_name']
                        req_user_id = data['user_id']
                        username = data['username']
                        is_public = data.get('is_public', True)
                        
                        # 验证用户ID与WebSocket连接的用户ID一致
                        if user_id != req_user_id:
                            raise ValueError("用户ID与连接不匹配")
                        
                        logger.info(f"创建房间: {room_name}, 用户: {username}({user_id}), 公开: {is_public}")
                        
                        # 缓存用户基本信息（仅在创建房间时）
                        await redis_client.save_user_info(user_id, {
                            "username": username,
                            "avatar": data.get("avatar", "")
                        })
                        
                        # 创建房间
                        room = await room_service.create_room(room_name, user_id, is_public)
                        room_code = room.invitation_code
                        
                        # 将用户添加到房间
                        await room_service.add_user_to_room(room.id, user_id, username)
                        
                        # 更新用户的当前房间
                        await redis_client.set(f"user:{user_id}:room", room_code)
                        
                        # 如果是公开房间，添加到公开房间列表
                        if is_public:
                            await redis_client.sadd("public_rooms", room_code)
                        
                        # 注册WebSocket到房间
                        message_service.register_connection(room.id, websocket)
                        
                        logger.info(f"房间创建成功: {room_code}")
                        
                        # 发送成功消息
                        await websocket.send_json({
                            "type": "room_created",
                            "room": room.dict(),
                            "message": "房间创建成功",
                            "users": [
                                {
                                    "id": user_id,
                                    "username": username,
                                    "status": "在线",
                                    "is_host": True,
                                    "avatar": data.get("avatar", "")
                                }
                            ]
                        })
                        
                    except Exception as e:
                        error_detail = traceback.format_exc()
                        logger.error(f"创建房间失败: {str(e)}")
                        logger.debug(error_detail)
                        
                        await websocket.send_json({
                            "type": "error",
                            "error": "创建房间失败",
                            "details": str(e),
                            "action": "create_room"
                        })
            
                elif message_type == "join_room":
                    # 2.加入房间
                    room_id = data["data"].get("room_id")
                    invitation_code = data["data"].get("invitation_code")
                    username = data["data"]["username"]
                    # 使用消息中提供的user_id，如果没有则使用路径参数中的user_id
                    user_id_from_data = data["data"].get("user_id")
                    actual_user_id = user_id_from_data if user_id_from_data else user_id
                    
                    # 缓存用户基本信息（仅在加入房间时才缓存）
                    avatar = data["data"].get("avatar", "")
                    await redis_client.save_user_info(actual_user_id, {
                        "username": username,
                        "avatar": avatar
                    })

                    try:
                        # 获取房间
                        room = None
                        if room_id:
                            room = await room_service.get_room_by_id(room_id)
                        elif invitation_code:
                            room = await room_service.get_room_by_code(invitation_code)

                        if not room:
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": "Room not found"}
                            })
                            continue

                        # 添加用户到房间
                        success = await room_service.add_user_to_room(room.id, actual_user_id, username)
                        if not success:
                            await websocket.send_json({
                                "type": "error",
                                "data": {"message": "Failed to join room"}
                            })
                            continue

                        # 注册WebSocket到房间
                        message_service.register_connection(room.id, websocket)
                        
                        # 获取房间所有用户ID
                        user_ids = await redis_client.get_room_users(room.id)
                        users = []
                        
                        # 获取每个用户的信息
                        for uid in user_ids:
                            # 获取用户信息
                            user_info = await redis_client.get_user_info(uid)
                            if not user_info:
                                # 如果缓存中没有，使用基本信息
                                users.append({
                                    "id": uid,
                                    "username": "用户" + uid[-6:],
                                    "status": "在线",
                                    "is_host": uid == room.host_id
                                })
                            else:
                                # 添加额外信息
                                users.append({
                                    "id": uid,
                                    "username": user_info.get("username", "用户" + uid[-6:]),
                                    "status": "在线",
                                    "is_host": uid == room.host_id,
                                    "avatar": user_info.get("avatar", "")
                                })

                        # 发送加入成功消息和用户列表
                        await websocket.send_json({
                            "type": "room_joined",
                            "data": {
                                "id": room.id,
                                "name": room.name,
                                "host_id": room.host_id,
                                "is_public": room.is_public,
                                "invitation_code": room.invitation_code,
                                "users": users
                            }
                        })

                        # 获取历史消息
                        history = await message_service.get_message_history(room.id)
                        await websocket.send_json({
                            "type": "message_history",
                            "data": {"messages": history}
                        })

                        # 广播用户加入消息
                        await message_service.broadcast_system_message(
                            room.id, f"{username} joined the room"
                        )
                        logger.info(f"User {actual_user_id} joined room {room.id}")
                    except Exception as e:
                        logger.error(f"Error joining room: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": f"Failed to join room: {str(e)}"}
                        })

                elif message_type == "message":
                    # 3.发送消息
                    room_id = data["data"]["room_id"]
                    content = data["data"]["content"]
                    username = data["data"]["username"]

                    try:
                        # 创建消息
                        message = Message.create_user_message(room_id, user_id, username, content)

                        # 广播消息
                        await message_service.broadcast_message(room_id, message.dict())
                        logger.info(f"Message sent in room {room_id} by user {user_id}")
                    except Exception as e:
                        logger.error(f"Error sending message: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": "Failed to send message"}
                        })

                elif message_type == "leave_room":
                    # 4.离开房间
                    room_id = data["data"]["room_id"]
                    username = data["data"]["username"]
                    # 使用消息中提供的user_id，如果没有则使用路径参数中的user_id
                    user_id_from_data = data["data"].get("user_id")
                    actual_user_id = user_id_from_data if user_id_from_data else user_id

                    try:
                        # 获取房间
                        room = await room_service.get_room_by_id(room_id)
                        if not room:
                            continue

                        # 发送离开成功消息
                        await websocket.send_json({
                            "type": "room_left",
                            "data": {"room_id": room_id}
                        })

                        # 广播用户离开消息
                        await message_service.broadcast_system_message(
                            room_id, f"{username} left the room"
                        )

                        # 取消注册WebSocket从房间
                        message_service.unregister_connection(room_id, websocket)

                        # 从房间移除用户
                        await room_service.remove_user_from_room(room_id, actual_user_id)
                        logger.info(f"User {actual_user_id} left room {room_id}")
                    except Exception as e:
                        logger.error(f"Error leaving room: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": f"Failed to leave room: {str(e)}"}
                        })

                elif message_type == "get_public_rooms":
                    # 5.获取公开房间列表
                    try:
                        public_rooms = await room_service.get_public_rooms()

                        # 发送公开房间列表
                        await websocket.send_json({
                            "type": "public_rooms",
                            "data": {
                                "rooms": [
                                    {
                                        "id": room.id,
                                        "name": room.name,
                                        "host_id": room.host_id,
                                        "user_count": len(room.users)
                                    } for room in public_rooms
                                ]
                            }
                        })
                    except Exception as e:
                        logger.error(f"Error getting public rooms: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "data": {"message": "Failed to get public rooms"}
                        })

            except json.JSONDecodeError:
                logger.error(f"无效的JSON数据: {data_raw}")
                await websocket.send_json({
                    "type": "error",
                    "error": "无效的请求格式",
                    "details": "请求必须是有效的JSON格式",
                    "action": "parse"
                })
            
            except Exception as e:
                error_detail = traceback.format_exc()
                logger.error(f"WebSocket消息处理失败: {str(e)}")
                logger.debug(error_detail)
                
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error": "消息处理失败",
                        "details": str(e)
                    })
                except:
                    # 如果发送错误消息失败，可能是连接已断开
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket连接断开: 用户ID={user_id}")
        connection_manager.disconnect(user_id)
        
        # 设置用户为离线状态
        await user_service.set_user_offline(user_id)
    except Exception as e:
        logger.error(f"WebSocket处理异常: {str(e)}")
        try:
            connection_manager.disconnect(user_id)
            # 设置用户为离线状态
            await user_service.set_user_offline(user_id)
        except:
            pass

@app.get("/")
async def read_root():
    """根路径API，主要用于前端接口诊断操作，判断后端是否正常连接？"""
    try:
        # 基本欢迎信息
        result = {
            "message": "欢迎来到谁是卧底的游戏！",
            "service_status": {
                "redis": "unavailable",
                "mongodb": "unavailable",
                "services_initialized": {
                    "user_service": user_service is not None,
                    "room_service": room_service is not None,
                    "message_service": message_service is not None
                }
            }
        }
        
        # 检查Redis连接
        if redis_client and redis_client._redis:
            try:
                # 测试Redis是否可用
                ping_result = await redis_client._redis.ping()
                result["service_status"]["redis"] = "available" if ping_result else "error"
            except Exception as e:
                result["service_status"]["redis_error"] = str(e)
        
        # 检查MongoDB连接
        if mongo_client:
            try:
                mongo_status = await mongo_client.check_connection_status()
                result["service_status"]["mongodb"] = "available" if mongo_status.get("connected") else "error"
                result["service_status"]["mongo_info"] = mongo_status
            except Exception as e:
                result["service_status"]["mongo_error"] = str(e)
        
        return result
    except Exception as e:
        logger.error(f"根路径诊断出错: {str(e)}")
        return {
            "message": "欢迎来到谁是卧底的游戏！",
            "error": str(e)
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=DEBUG)


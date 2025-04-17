"""
谁是卧底多人聊天系统v0.0.7

Description:
    提供给前端的API接口层、系统全局监测、websocket全局管理

Note:
    - 验证token+刷新redis TTL的http调用中间件
    - 应用程序开启、关闭检测
    - 根路径检测（提供给前端检测，之后可以删除）
    - websocket全局管理端口
    - 用户相关API：
        注册用户、登陆用户、登出用户、获取用户信息、刷新Access_token、刷新Refresh_token
    - 房间相关API：
        创建房间、删除房间
        刷新公共房间
        加入房间、退出房间
"""

import time
import json

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any
from pydantic import BaseModel
import jwt

from llm.llm_pipeline import llm_pipeline
from services.room_service import RoomService
from services.user_service import UserService
from services.auth_service import AuthService
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.logger_utils import setup_logger, get_logger
from config import (
    APP_HOST, APP_PORT, DEBUG,
    USER_STATUS_ONLINE, MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME,
    USER_STATUS_IN_ROOM
)
from utils.websocket_manager import WebSocketManager
from services.message_service import MessageService

# 配置日志
setup_logger("SpyAmongUs")
logger = get_logger(__name__)

# 数据模型
class UserRegister(BaseModel):
    """用户注册模型"""
    username: str
    password: str

class UserLogin(BaseModel):
    """用户登录模型"""
    username: str
    password: str

class TokenRefresh(BaseModel):
    """Token刷新模型"""
    refresh_token: str

# 初始化FastAPI应用
app = FastAPI(title="SpyAmongUs API", debug=DEBUG)

origins = [
    "http://localhost:5173",  # 前端开发服务器
    # 如果部署后前端地址不同，也需要添加
    # 例如: "http://your-frontend-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 初始化服务
redis_client = RedisClient()
mongo_client = MongoClient()
user_service = UserService(redis_client, mongo_client)
websocket_manager = WebSocketManager()
message_service = MessageService(redis_client, websocket_manager, llm_pipeline)
room_service = RoomService(user_service, redis_client, websocket_manager)
auth_service = AuthService()

# 设置服务之间的依赖关系
room_service.set_message_service(message_service)

# 验证token中间件
@app.middleware("http")
async def verify_token_middleware(request: Request, call_next):
    """验证token中间件，排除公开路径，验证其他所有请求的token"""
    # 不需要验证的路径
    public_paths = ["/api/register", "/api/login", "/api/refresh-token", "/api/token/refresh", "/"]
    current_path = request.url.path
    
    # 对OPTIONS请求放行（CORS预检请求）
    if request.method == "OPTIONS":
        logger.debug(f"OPTIONS预检请求，放行: {current_path}")
        return await call_next(request)
    
    # 放行这些路径
    if any(current_path == path for path in public_paths) or any(current_path.startswith(path + "/") for path in public_paths):
        logger.debug(f"公开路径，跳过验证: {current_path}")
        return await call_next(request)

    # 1. 获取Token
    auth_header = request.headers.get("Authorization")
    logger.debug(f"请求路径: {current_path}, Authorization头: {auth_header and '存在' or '不存在'}")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning(f"请求缺少有效Authorization头: {current_path}")
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "未提供有效的访问令牌"}
        )

    token = auth_header[7:]  # 移除Bearer前缀

    # 2. 验证Token
    is_valid, payload = auth_service.verify_token(token, "access")

    # 3. 处理验证结果
    if not is_valid:
        logger.warning(f"无效的访问令牌用于请求: {current_path}")
        # 尝试从无效token中提取user_id，仅用于尝试清理缓存
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})
            if "sub" in decoded:
                user_id_from_invalid_token = decoded["sub"]
                logger.info(f"尝试清理与无效token关联的用户缓存: {user_id_from_invalid_token}")
                await redis_client.delete_user_cache(user_id_from_invalid_token)
        except Exception as e:
            logger.error(f"从无效token提取或清理缓存失败: {str(e)}")
            
        # 严格返回401
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "无效的访问令牌"}
        )

    # 4. 提取用户信息
    user_id = payload.get("sub")
    username = payload.get("username")

    if not user_id:
        logger.error(f"有效Token但缺少'sub'字段: {current_path}")
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "令牌信息不完整"}
        )
        
    # 5. 设置请求状态
    request.state.user_id = user_id
    request.state.username = username

    # 6. 刷新Redis会话TTL
    await redis_client.refresh_user_session(user_id)
    logger.debug(f"用户 {user_id} 会话TTL已刷新")
    
    # 7. 继续处理请求
    return await call_next(request)

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化服务"""
    try:
        # 检查MongoDB连接状态
        mongo_status = await mongo_client.check_connection_status()
        if not mongo_status["connected"]:
            logger.error(f"MongoDB连接失败: {mongo_status['error']}")
            raise Exception("MongoDB连接失败")

        # 检查Redis连接状态
        redis_status = await redis_client.check_connection_status()
        if not redis_status["connected"]:
            logger.error(f"Redis连接失败: {redis_status['error']}")
            raise Exception("Redis连接失败")

        logger.info("应用初始化成功")

        # 启动WebSocket管理器的清理任务
        await websocket_manager.start()
    except Exception as e:
        logger.error(f"应用初始化失败: {str(e)}")
        raise
        
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    logger.info("应用关闭，开始清理资源...")

    # 关闭数据库连接
    await redis_client.disconnect()
    await mongo_client.disconnect()
    
    # 停止WebSocket管理器的清理任务
    await websocket_manager.stop()
    
    logger.info("资源清理完成，应用已安全关闭")

# API路由定义
@app.get("/")
async def read_root():
    """根路径API，用于前端接口诊断，判断后端是否正常连接"""
    try:
        # 基本欢迎信息
        result = {
            "message": "欢迎来到谁是卧底的游戏！",
            "version": "v0.0.5",
            "service_status": {
                "redis": "unavailable",
                "mongodb": "unavailable",
                "services_initialized": {
                    "user_service": user_service is not None,
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

# websocket相关
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """websocket端口控制"""
    await websocket.accept()

    # 获取认证信息
    try:
        # 首先尝试从URL查询参数获取token
        token = websocket.query_params.get("token")
        
        # 如果URL中没有token，尝试从第一条消息获取
        if not token:
            # 等待第一条消息中的token
            data = await websocket.receive_json()
            token = data.get("token")
        
        # 1.验证是否获取到token
        if not token:
            logger.warning(f"WebSocket连接 {room_id} 缺少token")
            await websocket.close(code=1008, reason="Missing authentication")
            return
            
        # 验证token
        is_valid, payload = auth_service.verify_token(token, "access")

        if not is_valid or 'sub' not in payload:
            logger.warning(f"WebSocket连接 {room_id} 的token无效")
            await websocket.close(code=1008, reason="Invalid authentication")
            return

        user_id = payload['sub']
        
        logger.info(f"用户 {user_id} 尝试连接房间 {room_id} 的WebSocket")

        # 2.验证用户是否在指定房间
        user_info = await user_service.get_user_info(user_id)
        
        # 获取用户在Redis中的原始数据，用于调试
        raw_user_data = await redis_client.get_user(user_id)
        logger.info(f"Redis中用户 {user_id} 的数据: {raw_user_data}")
        
        # 检查房间是否存在
        room_exists = await redis_client.check_room_exists(room_id)
        logger.info(f"房间 {room_id} 存在: {room_exists}")
        
        # 检查用户是否在房间的用户列表中
        is_user_in_room_list = await redis_client.is_user_in_room(room_id, user_id)
        logger.info(f"用户 {user_id} 在房间 {room_id} 的用户列表中: {is_user_in_room_list}")
        
        # 检查用户的current_room字段
        current_room = user_info["data"].get("current_room") if user_info["success"] else "无法获取"
        logger.info(f"用户 {user_id} 的current_room字段值: {current_room}")
        
        # 检查用户的status字段
        user_status = user_info["data"].get("status") if user_info["success"] else "无法获取"
        logger.info(f"用户 {user_id} 的status字段值: {user_status}")
        
        # 修改验证逻辑：只要用户在房间的users集合中或current_room匹配，就允许连接
        if not room_exists:
            logger.warning(f"房间 {room_id} 不存在，拒绝WebSocket连接")
            await websocket.close(code=1008, reason="Room does not exist")
            return
            
        # 判断用户是否有权限连接该房间
        is_allowed = False
        
        # 如果current_room匹配，允许连接
        if user_info["success"] and user_info["data"].get("current_room") == room_id:
            is_allowed = True
            logger.info(f"用户 {user_id} 的current_room字段匹配，允许连接")
            
        # 如果用户在房间的users集合中，允许连接
        elif is_user_in_room_list:
            is_allowed = True
            logger.info(f"用户 {user_id} 在房间users集合中，允许连接，并自动修复状态")
            
            # 修复用户状态和current_room
            await user_service.update_current_room(user_id, room_id)
            await user_service.update_user_status(user_id, USER_STATUS_IN_ROOM)
            logger.info(f"已更新用户 {user_id} 的current_room为 {room_id}，状态为 {USER_STATUS_IN_ROOM}")
            
        if not is_allowed:
            logger.warning(f"用户 {user_id} 无权连接房间 {room_id} 的WebSocket")
            await websocket.close(code=1008, reason="User not in this room")
            return

        # 3.添加到连接管理器
        await websocket_manager.add_connection(room_id, user_id, websocket)
        logger.info(f"用户 {user_id} 已添加到房间 {room_id} 的WebSocket连接管理器")

        # --- 获取房间信息并确定上下文 ---
        room_info = await room_service.get_room_basic_data(room_id)
        context = "join"
        room_name = "未知房间"
        if room_info and room_info.get("host_id") == user_id:
            context = "create"
        if room_info and room_info.get("room_name"):
            room_name = room_info["room_name"]
        logger.info(f"用户 {user_id} 连接房间 {room_id} 的上下文: {context}, 房间名: {room_name}")
        # ---------------------------------

        # 4.发送连接成功消息 (添加 context 和 room_name)
        await websocket.send_json({
            "type": "system",
            "event": "connected",
            "room_id": room_id,
            "context": context, # 添加上下文
            "room_name": room_name, # 添加房间名
            "timestamp": int(time.time() * 1000)
        })
        logger.info(f"已向用户 {user_id} 发送WebSocket连接成功消息 (含上下文)")

        # 5.监听消息
        while True:
            try:
                # 等待消息
                raw_message = await websocket.receive_text()
                
                # 解析消息内容
                try:
                    message_data = json.loads(raw_message)
                    
                    # 收到任何有效消息后，更新活动时间戳
                    await websocket_manager.update_connection_state(room_id, user_id)
                    logger.debug(f"用户 {user_id} 在房间 {room_id} 的活动时间已更新")
                    
                    # 处理心跳消息
                    if message_data.get("type") == "ping":
                        # 立即回复pong心跳响应
                        logger.debug(f"收到用户 {user_id} 的ping心跳，立即回复pong")
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": int(time.time() * 1000)
                        })
                        continue
                    
                    # 处理所有普通消息
                    logger.info(f"收到WebSocket消息: {message_data}")
                    
                    # 确保消息包含必要字段
                    if "room_id" not in message_data:
                        message_data["room_id"] = room_id
                    
                    if "user_id" not in message_data:
                        message_data["user_id"] = user_id
                    
                    # 根据消息类型处理
                    if message_data.get("type") == "secret":
                        logger.info("处理秘密消息")
                        result = await message_service.process_secret_message(room_id, message_data, user_id)
                    else:
                        logger.info("处理普通消息")
                        result = await message_service.process_message(message_data)
                    
                    # 检查处理结果
                    logger.info(f"消息处理结果: {result}")
                    
                    # 如果处理失败，发送错误响应
                    if not result.get("success", False):
                        error_msg = result.get("message", "处理消息失败")
                        logger.error(f"消息处理失败: {error_msg}")
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg,
                            "timestamp": int(time.time() * 1000)
                        })
                        
                except json.JSONDecodeError:
                    logger.error(f"收到无效JSON消息: {raw_message}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "消息格式无效",
                        "timestamp": int(time.time() * 1000)
                    })
                    
            except Exception as e:
                logger.error(f"处理WebSocket消息时出错: {str(e)}")
                # 发送错误信息但不断开连接
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"服务器处理消息时出错: {str(e)}",
                        "timestamp": int(time.time() * 1000)
                    })
                except:
                    # 如果无法发送，可能连接已断开
                    break

    except WebSocketDisconnect:
        # 6.用户断开连接（缓存清理逻辑放至room_service）
        try:
            if 'user_id' in locals() and 'room_id' in locals():
                await websocket_manager.remove_user_connection(room_id, user_id)
        except:
            pass
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        try:
            await websocket.close(code=1011, reason="Server error")
        except:
            pass


# 用户认证相关API
@app.post("/api/register")
async def register(user_data: Dict[str, str]):
    """用户注册API"""
    try:
        result = await user_service.register(user_data["username"], user_data["password"])
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"用户注册失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
async def login(user_data: Dict[str, str]):
    """用户登录API"""
    try:
        result = await user_service.login(user_data["username"], user_data["password"])
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"用户登录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/logout")
async def logout(request: Request):
    """用户登出API"""
    try:
        # 从请求状态中获取用户ID（中间件已验证）
        user_id = request.state.user_id

        result = await user_service.logout(user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except AttributeError as ae:
        # 处理request.state.user_id不存在的情况
        logger.error(f"登出时属性错误: {str(ae)}")
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"用户登出失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{user_id}")
async def get_user_info(user_id: str, request: Request):
    """获取用户信息API"""
    try:
        logger.debug(f"获取用户信息请求: 目标用户ID={user_id}, 请求用户ID={getattr(request.state, 'user_id', 'unknown')}")
        
        # 检查当前登录用户是否有权限访问此信息
        if not hasattr(request.state, 'user_id'):
            logger.warning(f"尝试访问用户信息但未经身份验证: 目标={user_id}")
            raise HTTPException(status_code=401, detail="未授权，请重新登录")
            
        if request.state.user_id != user_id:
            logger.warning(f"用户尝试访问其他用户信息: 请求用户={request.state.user_id}, 目标用户={user_id}")
            raise HTTPException(status_code=403, detail="无权访问此用户信息")
            
        result = await user_service.get_user_info(user_id)
        if not result["success"]:
            logger.warning(f"获取用户信息失败: {result['message']}")
            raise HTTPException(status_code=404, detail=result["message"])
            
        logger.debug(f"成功获取用户信息: {user_id}")
        return result
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"获取用户信息发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/token/refresh")
async def refresh_token(request: Request):
    """刷新访问令牌API

    从refresh_token获取新的access_token，保持用户登录状态
    """
    try:
        # 1. 获取refresh_token
        refresh_token = None

        # 尝试从请求体JSON中获取
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
            if refresh_token:
                logger.debug("成功从JSON请求体获取refresh_token")
        except:
            logger.debug("请求体不是有效的JSON格式")

        # 如果未从JSON获取到，尝试从表单中获取
        if not refresh_token:
            try:
                form = await request.form()
                refresh_token = form.get("refresh_token")
                if refresh_token:
                    logger.debug("成功从表单获取refresh_token")
            except:
                logger.debug("请求体不是有效的表单格式")

        # 最后尝试从查询参数获取
        if not refresh_token:
            refresh_token = request.query_params.get("refresh_token")
            if refresh_token:
                logger.debug("成功从查询参数获取refresh_token")

        # 2. 验证是否获取到refresh_token
        if not refresh_token:
            logger.warning("刷新令牌请求缺少refresh_token参数")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "缺少refresh_token参数"
                }
            )

        # 3. 使用auth_service刷新访问令牌
        new_access_token = auth_service.refresh_access_token(refresh_token)

        # 4. 检查返回结果
        if not new_access_token:
            logger.warning("无效的刷新令牌")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的刷新令牌"
                }
            )

        # 5. 返回新的访问令牌
        logger.info("访问令牌刷新成功")
        return {
            "success": True,
            "message": "访问令牌刷新成功",
            "data": {
                "access_token": new_access_token
            }
        }

    except Exception as e:
        logger.error(f"刷新访问令牌过程中发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"刷新访问令牌失败: {str(e)}"
            }
        )

@app.post("/api/token/rotate")
async def rotate_token(request: Request):
    """轮换令牌API

    在安全事件发生时，同时刷新访问令牌和刷新令牌
    """
    try:
        # 1. 获取refresh_token
        refresh_token = None

        # 尝试从请求体JSON中获取
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
            if refresh_token:
                logger.debug("成功从JSON请求体获取refresh_token")
        except:
            logger.debug("请求体不是有效的JSON格式")

        # 如果未从JSON获取到，尝试从表单中获取
        if not refresh_token:
            try:
                form = await request.form()
                refresh_token = form.get("refresh_token")
                if refresh_token:
                    logger.debug("成功从表单获取refresh_token")
            except:
                logger.debug("请求体不是有效的表单格式")

        # 最后尝试从查询参数获取
        if not refresh_token:
            refresh_token = request.query_params.get("refresh_token")
            if refresh_token:
                logger.debug("成功从查询参数获取refresh_token")

        # 2. 验证是否获取到refresh_token
        if not refresh_token:
            logger.warning("令牌轮换请求缺少refresh_token参数")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "缺少refresh_token参数"
                }
            )

        # 3. 从令牌中提取用户ID
        user_id = auth_service.get_user_id_from_token(refresh_token, "refresh")
        if not user_id:
            logger.warning("无法从刷新令牌中提取用户ID")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的刷新令牌"
                }
            )

        # 4. 获取用户信息，用于创建新令牌
        user_data = await redis_client.get_user(user_id)
        if not user_data or "username" not in user_data:
            logger.warning(f"用户信息不存在或已过期: {user_id}")
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "message": "用户信息不存在或已过期"
                }
            )

        username = user_data.get("username")

        # 5. 轮换刷新令牌
        new_refresh_token = auth_service.rotate_refresh_token(refresh_token)
        if not new_refresh_token:
            logger.warning("轮换刷新令牌失败")
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "无效的刷新令牌"
                }
            )

        # 6. 创建新的访问令牌
        access_token, _ = auth_service.create_tokens(user_id, username)

        # 7. 返回新的令牌对
        logger.info(f"用户 {user_id} 令牌轮换成功")
        return {
            "success": True,
            "message": "令牌已完全更新",
            "data": {
                "access_token": access_token,
                "refresh_token": new_refresh_token
            }
        }

    except Exception as e:
        logger.error(f"轮换令牌过程中发生错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"轮换令牌失败: {str(e)}"
            }
        )


# 房间相关API
@app.get("/api/room/{invite_code}")
async def get_room_details(invite_code: str):
    """获取房间详细信息API"""
    try:
        # 调用RoomService获取房间详情
        result = await room_service.get_room_details(invite_code)
        
        if not result["success"]:
            # 根据错误消息决定状态码
            status_code = 404 if "不存在" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        
        # 直接返回业务层的结果，已包含 room_data
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取房间 {invite_code} 详情时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取房间详情失败: {str(e)}")

@app.post("/api/room/create_room")
async def create_room(room_data: Dict[str, Any], request: Request):
    """创建房间API"""
    try:
        # 从请求状态中获取用户ID
        user_id = request.state.user_id
        username = getattr(request.state, 'username', '用户')

        # 调用房间服务创建房间
        result = await room_service.create_room(room_name=room_data.get("room_name", f"{username}的房间"),
                                                host_id=user_id, is_public=room_data.get("is_public", True),
                                                total_players=room_data.get("total_players", MIN_PLAYERS),
                                                spy_count=room_data.get("spy_count", MIN_SPY_COUNT),
                                                max_rounds=room_data.get("max_rounds", MAX_ROUNDS),
                                                speak_time=room_data.get("speak_time", MAX_SPEAK_TIME),
                                                last_words_time=room_data.get("last_words_time", MAX_LAST_WORDS_TIME),
                                                llm_free=room_data.get("llm_free", False))

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        # 直接返回服务层简化后的结果 {success, message, data:{invite_code}}
        return result
    except AttributeError:
        # 处理request.state.user_id不存在的情况
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"创建房间失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/room/{invite_code}/delete_room")
async def delete_room(invite_code: str, request: Request):
    """删除房间API"""
    try:
        # 从请求状态中获取用户ID
        user_id = request.state.user_id

        # 调用房间服务删除房间
        result = await room_service.delete_room(invite_code, user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        # 直接返回服务层的结果 {success, message, data:{reason}}
        return result
    except AttributeError:
        # 处理request.state.user_id不存在的情况
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"删除房间失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rooms/refresh_public_room")
async def refresh_public_rooms():
    """刷新获取公开房间列表API"""
    try:
        result = await room_service.get_public_rooms()
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"获取公开房间列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/room/{invite_code}/join_room")
async def join_room(invite_code: str, request: Request):
    """加入房间API"""
    try:
        # 从请求状态中获取用户ID
        user_id = request.state.user_id
        
        # 调用房间服务加入房间
        result = await room_service.join_room(invite_code, user_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        # 直接返回服务层简化后的结果 {success, message}
        return result
    except AttributeError:
        # 处理request.state.user_id不存在的情况
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"加入房间失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/room/{invite_code}/leave_room")
async def leave_room(invite_code: str, request: Request):
    """退出房间API"""
    try:
        # 从请求状态中获取用户ID
        user_id = request.state.user_id
        
        # 调用房间服务退出房间
        result = await room_service.leave_room(invite_code, user_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        # 直接返回服务层的结果 {success, message}
        return result
    except AttributeError:
        # 处理request.state.user_id不存在的情况
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"退出房间失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=DEBUG)


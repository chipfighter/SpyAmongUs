"""
核心文件：多人聊天系统v0.0.5
"""
import time
import json

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any
from pydantic import BaseModel
import jwt
from fastapi import WebSocket, WebSocketDisconnect

from services.room_service import RoomService
from services.user_service import UserService
from services.auth_service import AuthService
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.logger_utils import setup_logger, get_logger
from config import (
    APP_HOST, APP_PORT, DEBUG,
    USER_STATUS_ONLINE, MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME
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

# CORS设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # 测试环境不限制，生产环境需修改
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化服务
redis_client = RedisClient()
mongo_client = MongoClient()
user_service = UserService(redis_client)
websocket_manager = WebSocketManager()
message_service = MessageService(redis_client, websocket_manager)
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
            await websocket.close(code=1008, reason="Missing authentication")
            return
            
        # 验证token
        is_valid, payload = auth_service.verify_token(token, "access")

        if not is_valid or 'sub' not in payload:
            await websocket.close(code=1008, reason="Invalid authentication")
            return

        user_id = payload['sub']

        # 2.验证用户是否在指定房间
        user_info = await user_service.get_user_info(user_id)
        if not user_info["success"] or user_info["data"].get("current_room") != room_id:
            await websocket.close(code=1008, reason="User not in this room")
            return

        # 3.添加到连接管理器
        await websocket_manager.add_connection(room_id, user_id, websocket)

        # 4.发送连接成功消息
        await websocket.send_json({
            "type": "system",
            "event": "connected",
            "room_id": room_id,
            "timestamp": int(time.time() * 1000)
        })

        # 5.监听消息
        while True:
            try:
                # 等待消息
                raw_message = await websocket.receive_text()
                
                # 解析消息内容
                try:
                    message_data = json.loads(raw_message)
                    
                    # 处理消息
                    result = await message_service.process_message(room_id, message_data, user_id)
                    
                    # 如果处理失败，发送错误响应
                    if not result["success"]:
                        await websocket.send_json({
                            "type": "error",
                            "message": result["message"],
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
                        "message": "服务器处理消息时出错",
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
@app.post("/api/room/create")
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
            
        # 添加WebSocket连接信息到响应中
        if "data" in result and "invite_code" in result["data"]:
            result["data"]["ws_endpoint"] = f"/ws/{result['data']['invite_code']}"
            
        return result
    except AttributeError:
        # 处理request.state.user_id不存在的情况
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"创建房间失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/room/{invite_code}/delete")
async def delete_room(invite_code: str, request: Request):
    """删除房间API"""
    try:
        # 从请求状态中获取用户ID
        user_id = request.state.user_id

        # 调用房间服务删除房间
        result = await room_service.delete_room(invite_code, user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except AttributeError:
        # 处理request.state.user_id不存在的情况
        raise HTTPException(status_code=401, detail="未授权，请重新登录")
    except Exception as e:
        logger.error(f"删除房间失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rooms/public")
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

if __name__ == "__main__":
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=DEBUG)


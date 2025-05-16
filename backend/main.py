"""
谁是卧底多人聊天系统v0.0.8

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
import asyncio
import logging

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
from services.feedback_service import FeedbackService
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.logger_utils import setup_logger, get_logger
from config import (
    APP_HOST, APP_PORT, DEBUG,
    USER_STATUS_ONLINE, MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME,
    USER_STATUS_IN_ROOM, ROOM_KEY_PREFIX, GAME_STATUS_PLAYING, ROOM_ALIVE_PLAYERS_KEY_PREFIX
)
from utils.websocket_manager import WebSocketManager
from services.message_service import MessageService

# 配置日志（当前根路径是）
setup_logger("SpyAmongUs")
logger = get_logger(__name__)

game_service_logger = setup_logger("services.game_service", level=logging.DEBUG)
debug_logger = setup_logger("debug", level=logging.DEBUG, log_file="game_debug.log")

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
    "http://localhost:5173",  # 前端本地开发服务器
    # 如果部署后前端地址不同，也需要添加
    # 例如: "http://your-frontend-domain.com"
    # 前端放到CDN上也需要注意CORS跨域问题
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
feedback_service = FeedbackService(mongo_client)

# 设置服务之间的依赖关系
room_service.set_message_service(message_service)
# 获取GameService实例
game_service = room_service.game_service
# MessageService和GameService之间的双向引用
message_service.set_game_service(game_service)
game_service.set_message_service(message_service)
# 设置GameService的LLM Pipeline
game_service.set_llm_pipeline(llm_pipeline)

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

        # 注意: GameService已在RoomService初始化时创建
        logger.info("RoomService中的GameService已初始化")

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

        room_info = await room_service.get_room_basic_data(room_id)
        context = "join"
        room_name = "未知房间"
        if room_info and room_info.get("host_id") == user_id:
            context = "create"
        if room_info and room_info.get("room_name"):
            room_name = room_info["room_name"]
        logger.info(f"用户 {user_id} 连接房间 {room_id} 的上下文: {context}, 房间名: {room_name}")

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
        
        # 获取房间用户列表，并发送给客户端
        try:
            room_data = await room_service.get_room_data_users(room_id)
            if room_data["success"] and "room_data" in room_data["data"]:
                users_list = room_data["data"]["room_data"].get("users", [])
                # 发送user_list_update消息给刚连接的客户端
                await websocket.send_json({
                    "type": "user_list_update",
                    "users": users_list,
                    "timestamp": int(time.time() * 1000)
                })
                logger.info(f"已向用户 {user_id} 发送房间用户列表，共 {len(users_list)} 名用户")
        except Exception as e:
            logger.error(f"发送房间用户列表失败: {str(e)}")

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
                    
                    # 处理上帝角色回应消息
                    if message_data.get("type") == "god_role_response":
                        logger.info(f"处理上帝角色回应: {message_data}")
                        await room_service.game_service.handle_god_response(user_id, message_data)
                        continue
                    
                    # 处理上帝选词消息
                    if message_data.get("type") == "god_words_selected":
                        logger.info(f"处理上帝选词: {message_data}")
                        # 获取词语数据
                        civilian_word = message_data.get("civilian_word", "")
                        spy_word = message_data.get("spy_word", "")
                        
                        if not civilian_word or not spy_word:
                            logger.error(f"词语数据不完整: civilian_word={civilian_word}, spy_word={spy_word}")
                            await websocket.send_json({
                                "type": "error",
                                "message": "词语数据不完整",
                                "timestamp": int(time.time() * 1000)
                            })
                            continue
                        
                        # 广播消息给所有玩家，通知他们上帝已选词
                        await websocket_manager.broadcast_message(
                            room_id,
                            {
                                "type": "god_words_selected",
                                "message": "上帝已选择词语，游戏正在初始化...",
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        
                        # 调用游戏服务的初始化方法
                        await room_service.game_service.initialize_game(room_id, civilian_word, spy_word)
                        
                        continue
                    
                    # 处理上帝选词超时消息
                    if message_data.get("type") == "god_words_selection_timeout":
                        logger.info(f"处理上帝选词超时: {message_data}")
                        # 广播消息给所有玩家
                        await websocket_manager.broadcast_message(
                            room_id,
                            {
                                "type": "god_words_selection_timeout",
                                "message": "上帝选词超时，由场外AI模拟上帝",
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        
                        continue
                    
                    # 处理遗言消息
                    if message_data.get("type") == "last_words":
                        logger.info(f"处理玩家遗言: {message_data}")
                        
                        # 调用游戏服务处理遗言
                        result = await room_service.game_service.handle_last_words(
                            room_id=room_id,
                            player_id=user_id,
                            message=message_data
                        )
                        
                        # 检查处理结果
                        if not result.get("success", False):
                            error_msg = result.get("message", "处理遗言失败")
                            logger.error(f"遗言处理失败: {error_msg}")
                            await websocket.send_json({
                                "type": "error",
                                "message": error_msg,
                                "timestamp": int(time.time() * 1000)
                            })
                        
                        continue
                    
                    # 处理放弃遗言消息
                    if message_data.get("type") == "skip_last_words":
                        logger.info(f"玩家 {user_id} 放弃遗言")
                        
                        # 获取房间基本信息
                        room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                        room_data = await redis_client.get_room_basic_data(room_id)
                        last_words_player = room_data.get("last_words_player")
                        
                        # 检查是否是当前遗言玩家
                        if last_words_player != user_id:
                            logger.warning(f"玩家 {user_id} 无权放弃遗言，当前遗言玩家为 {last_words_player}")
                            await websocket.send_json({
                                "type": "error",
                                "message": "你没有权限放弃遗言",
                                "timestamp": int(time.time() * 1000)
                            })
                            continue
                        
                        # 广播玩家放弃遗言消息
                        await websocket_manager.broadcast_message(
                            room_id,
                            {
                                "type": "last_words_skipped",
                                "player_id": user_id,
                                "message": "玩家放弃遗言",
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        
                        # 清除遗言玩家信息
                        await redis_client.hdel(room_key, "last_words_player")
                        
                        # 等待1.5秒，保持与正常遗言流程一致
                        await asyncio.sleep(1.5)
                        
                        # 检查游戏是否结束
                        game_end_result = await room_service.game_service.check_game_end_condition(room_id)
                        
                        if game_end_result["game_end"]:
                            # 游戏结束，广播游戏结果
                            await room_service.game_service.broadcast_game_result(room_id, game_end_result)
                        else:
                            # 游戏未结束，进入下一轮
                            await room_service.game_service.start_next_round(room_id)
                        
                        continue
                    
                    # 处理投票消息
                    if message_data.get("type") == "vote":
                        logger.info(f"收到玩家 {user_id} 的投票消息: {message_data}")
                        
                        # 获取投票目标ID
                        target_id = message_data.get("target_id")
                        if not target_id:
                            logger.warning(f"玩家 {user_id} 发送的投票消息缺少target_id")
                            await websocket.send_json({
                                "type": "error",
                                "message": "投票消息缺少目标玩家ID",
                                "timestamp": int(time.time() * 1000)
                            })
                            continue
                        
                        # 调用游戏服务处理投票
                        result = await room_service.game_service.handle_player_vote(
                            room_id=room_id,
                            voter_id=user_id,
                            target_id=target_id
                        )
                        
                        # 检查处理结果
                        if not result.get("success", False):
                            error_msg = result.get("message", "处理投票失败")
                            logger.error(f"处理投票失败: {error_msg}")
                            await websocket.send_json({
                                "type": "error",
                                "message": error_msg,
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
                
                # 检查是否是游戏进行时
                try:
                    # 获取房间当前状态
                    room_key = f"{ROOM_KEY_PREFIX}{room_id}"
                    room_status = await redis_client.hget(room_key, "status")
                    current_phase = await redis_client.hget(room_key, "current_phase")
                    
                    # 如果游戏正在进行中且处于发言阶段，尝试恢复游戏流程
                    if room_status == GAME_STATUS_PLAYING and current_phase == "speaking":
                        logger.warning(f"游戏正在进行中，尝试恢复发言流程: 房间={room_id}, 阶段={current_phase}")
                        # 获取当前发言者
                        alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
                        try:
                            current_speaker = await redis_client.zrange(alive_players_key, 0, 0)
                            if current_speaker and len(current_speaker) > 0 and current_speaker[0].startswith("llm_player_"):
                                logger.info(f"当前发言者是AI玩家 {current_speaker[0]}，尝试移动到下一个发言者")
                                # 使用room_service的game_service移动到下一个发言者
                                await room_service.game_service.move_to_next_speaker(room_id)
                        except Exception as recovery_error:
                            logger.error(f"尝试恢复游戏流程失败: {str(recovery_error)}")
                except Exception as check_error:
                    logger.error(f"检查游戏状态失败: {str(check_error)}")

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
        result = await room_service.get_room_data_users(invite_code)
        
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

@app.post("/api/room/{invite_code}/ready")
async def update_ready_status(invite_code: str, request: Request):
    """切换用户在指定房间的准备状态"""
    # 从中间件设置的 request state 获取对应的 user_id
    user_id = request.state.user_id
    logger.debug(f"用户 {user_id} 尝试切换房间 {invite_code} 的准备状态")

    # 调用 RoomService 中的方法
    result = await room_service.toggle_user_ready(user_id, invite_code)

    if result["success"]:
        logger.info(f"用户 {user_id} 在房间 {invite_code} 切换准备状态成功")
        return JSONResponse(status_code=200, content=result)
    else:
        logger.warning(f"用户 {user_id} 在房间 {invite_code} 切换准备状态失败: {result['message']}")
        raise HTTPException(status_code=400, detail=result["message"])

# 添加投票API
@app.post("/api/room/{invite_code}/vote")
async def submit_vote(invite_code: str, vote_data: Dict[str, Any], request: Request):
    """
    提交玩家投票
    
    Args:
        invite_code: 房间邀请码
        vote_data: 投票数据，包含target_id和vote_time
    """
    try:
        # 1. 验证用户身份和权限
        user_id = request.state.user_id
        username = request.state.username
        
        if not user_id:
            logger.warning(f"未授权的投票请求: {invite_code}")
            return JSONResponse(
                status_code=401,
                content={"status": "error", "message": "未授权的请求"}
            )
        
        # 2. 获取投票目标和时间
        target_id = vote_data.get("target_id")
        vote_time = vote_data.get("vote_time", 0.0)
        
        if not target_id:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "缺少投票目标ID"}
            )
        
        # 3. 处理投票
        game_result = await game_service.handle_player_vote(invite_code, user_id, target_id)
        
        # 4. 返回处理结果
        if game_result.get("success", False):
            return JSONResponse(
                status_code=200,
                content={"status": "success", "message": game_result.get("message", "投票成功"), "data": game_result.get("data", {})}
            )
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": game_result.get("message", "投票失败")}
            )
        
    except Exception as e:
        logger.error(f"处理投票请求失败: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"服务器错误: {str(e)}"}
        )

# 用户信息修改相关API
@app.post("/api/user/{user_id}/update_password")
async def update_password(user_id: str, password_data: Dict[str, str], request: Request):
    """更新用户密码API"""
    try:
        # 验证权限
        if not hasattr(request.state, 'user_id'):
            raise HTTPException(status_code=401, detail="未授权，请重新登录")
            
        if request.state.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权修改此用户密码")
        
        # 更新密码
        result = await user_service.update_password(
            user_id, 
            password_data["old_password"], 
            password_data["new_password"]
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户密码发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user/{user_id}/update_avatar")
async def update_avatar(user_id: str, avatar_data: Dict[str, str], request: Request):
    """更新用户头像API"""
    try:
        # 验证权限
        if not hasattr(request.state, 'user_id'):
            raise HTTPException(status_code=401, detail="未授权，请重新登录")
            
        if request.state.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权修改此用户头像")
        
        # 更新头像
        result = await user_service.update_avatar(user_id, avatar_data["avatar_url"])
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新用户头像发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 反馈相关API
@app.post("/api/feedback/submit")
async def submit_feedback(feedback_data: Dict[str, Any], request: Request):
    """提交用户反馈API"""
    try:
        # 获取用户ID (如果授权了)
        user_id = getattr(request.state, 'user_id', None)
        username = getattr(request.state, 'username', '匿名用户')
        
        # 处理反馈数据
        # 如果前端传来user_id不是anonymous但请求没有授权，将其设为匿名
        if feedback_data.get("user_id") and feedback_data["user_id"] != "anonymous" and not user_id:
            logger.warning("未授权用户尝试使用非匿名ID提交反馈，已转为匿名提交")
            feedback_data["user_id"] = "anonymous"
        
        # 如果前端提交的user_id与授权用户不匹配，使用授权用户的ID
        if user_id and feedback_data.get("user_id") and feedback_data["user_id"] != "anonymous" and feedback_data["user_id"] != user_id:
            logger.info(f"用户提交反馈用户ID不匹配，使用授权ID: {user_id}")
            feedback_data["user_id"] = user_id
            feedback_data["username"] = username
        
        # 如果已授权但未指定用户ID，则使用授权用户ID
        if user_id and (not feedback_data.get("user_id") or feedback_data.get("user_id") == "anonymous"):
            feedback_data["user_id"] = user_id
            feedback_data["username"] = username
                
        # 处理反馈提交
        result = await feedback_service.submit_feedback(feedback_data)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交反馈时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 管理员反馈获取API
@app.get("/api/admin/feedbacks")
async def get_all_feedbacks(
    request: Request,
    status: str = None,
    type: str = None
):
    """管理员获取所有反馈API"""
    try:
        # 验证管理员权限
        if not hasattr(request.state, 'user_id'):
            raise HTTPException(status_code=401, detail="未授权，请重新登录")
            
        # TODO: 在实际环境中，应该检查用户是否有管理员权限
        # 此处简化处理，假设所有登录用户均可访问管理员API
        
        # 获取反馈列表
        result = await feedback_service.get_all_feedbacks(status=status, type=type)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取反馈列表时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 更新反馈状态API
@app.post("/api/admin/feedback/{feedback_id}/update-status")
async def update_feedback_status(
    feedback_id: str,
    status_data: Dict[str, str],
    request: Request
):
    """更新反馈状态API"""
    try:
        # 验证管理员权限
        if not hasattr(request.state, 'user_id'):
            raise HTTPException(status_code=401, detail="未授权，请重新登录")
            
        # TODO: 在实际环境中，应该检查用户是否有管理员权限
        
        # 更新反馈状态
        new_status = status_data.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="缺少状态字段")
            
        result = await feedback_service.update_feedback_status(feedback_id, new_status)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
            
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新反馈状态时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)


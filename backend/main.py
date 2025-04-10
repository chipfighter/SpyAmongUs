"""
核心文件：多人聊天系统v0.0.4
"""

import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict, List, Set
import time
import asyncio
from pydantic import BaseModel

# 移除 RoomService 导入
from services.user_service import UserService
from services.message_service import MessageService
from services.auth_service import AuthService
from utils.redis_utils import RedisClient
from utils.mongo_utils import MongoClient
from utils.logger_utils import setup_logger, get_logger
from config import (
    APP_HOST, APP_PORT, DEBUG,
    USER_STATUS_ONLINE
)

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

# WebSocket连接管理
class ConnectionManager:
    """管理所有与服务器的WebSocket连接"""
    
    def __init__(self):
        """初始化连接管理器"""
        # 存储所有活跃的WebSocket连接: {user_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, user_id: str, websocket: WebSocket):
        """添加WebSocket连接到管理器"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"用户 {user_id} 连接成功")
    
    def disconnect(self, user_id: str):
        """断开并移除用户WebSocket连接"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"用户 {user_id} 断开连接")
    
    async def send_json(self, user_id: str, message: dict):
        """向特定用户发送JSON消息"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
            
    def disconnect_all(self):
        """断开所有连接"""
        self.active_connections = {}
        logger.info("所有WebSocket连接已断开")

# WebSocket消息类型常量
MESSAGE_TYPES = {
    # 连接相关
    'AUTH': 'auth',
    'CONNECTION_ESTABLISHED': 'connection_established',
    'HEARTBEAT': 'heartbeat',
    
    # 用户状态相关
    'USER_STATUS_UPDATE': 'user_status_update',
    
    # 消息相关
    'MESSAGE': 'message',
    
    # 错误处理
    'ERROR': 'error'
}

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

# 初始化服务和客户端
redis_client = RedisClient()
mongo_client = MongoClient()
connection_manager = ConnectionManager()
user_service = UserService(redis_client, mongo_client)
message_service = MessageService(redis_client)
auth_service = AuthService()

# 验证token和刷新Redis TTL
@app.middleware("http")
async def verify_token_middleware(request: Request, call_next):
    """验证token中间件，排除公开路径，验证其他所有请求的token"""
    # 不需要验证的路径
    public_paths = ["/api/register", "/api/login", "/api/refresh-token", "/"]
    
    # 放行这些路径
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)

    # 获取token
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "未提供访问令牌"}
        )
    
    # 格式化token
    token = auth_header
    if token.startswith("Bearer "):
        token = token[7:]  # 移除Bearer前缀

    # 验证token
    is_valid, payload = auth_service.verify_token(token, "access")
    if not is_valid:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "无效的访问令牌"}
        )

    # 刷新Redis TTL
    user_id = payload.get("sub")
    if user_id:
        await redis_client.refresh_user_session(user_id)

    # 将用户信息添加到请求中
    request.state.user_id = user_id
    request.state.username = payload.get("username")

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
    
    # 断开所有WebSocket连接
    connection_manager.disconnect_all()
    
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
            "version": "v0.0.4",
            "service_status": {
                "redis": "unavailable",
                "mongodb": "unavailable",
                "services_initialized": {
                    "user_service": user_service is not None,
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

# 用户认证相关API
@app.post("/api/register")
async def register(user_data: Dict[str, str]):
    """用户注册API"""
    try:
        result = await user_service.register_user(user_data["username"], user_data["password"])
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
async def logout(user_data: Dict[str, str]):
    """用户登出API"""
    try:
        # 从请求体中获取用户ID
        user_id = user_data.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="未提供用户ID")
        
        result = await user_service.logout(user_id)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"用户登出失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/{user_id}")
async def get_user_info(user_id: str):
    """获取用户信息API"""
    try:
        result = await user_service.get_user_info(user_id)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"获取用户信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/token/refresh")
async def refresh_token(refresh_token: str):
    """刷新访问令牌API"""
    try:
        result = await user_service.refresh_token(refresh_token)
        if not result["success"]:
            raise HTTPException(status_code=401, detail=result["message"])
        return result
    except Exception as e:
        logger.error(f"刷新令牌失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=DEBUG)


"""
谁是卧底多人聊天系统v0.0.8

Description:
    应用入口 — FastAPI 初始化、中间件、生命周期钩子、路由注册
    所有 API 端点已拆分至 routers/ 子模块

Note:
    - 验证token+刷新redis TTL的http调用中间件
    - 应用程序开启、关闭检测
    - 根路径检测（提供给前端检测，之后可以删除）
"""

import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import jwt

from utils.logger_utils import setup_logger, get_logger
from config import APP_HOST, APP_PORT, DEBUG

# ── 日志配置 ──────────────────────────────────────────────
setup_logger("SpyAmongUs")
logger = get_logger(__name__)

game_service_logger = setup_logger("services.game_service", level=logging.DEBUG)
debug_logger = setup_logger("debug", level=logging.DEBUG, log_file="game_debug.log")

# ── 导入服务实例（来自 dependencies.py） ──────────────────
from dependencies import (
    redis_client, mongo_client, user_service,
    websocket_manager, auth_service
)

# ── 导入路由模块 ──────────────────────────────────────────
from routers import auth, room, game, user, feedback, admin, websocket as ws_router

# ── 初始化 FastAPI 应用 ───────────────────────────────────
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

# ── 注册路由 ──────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(room.router)
app.include_router(game.router)
app.include_router(user.router)
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(ws_router.router)

# ── 验证token中间件 ──────────────────────────────────────
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

# ── 生命周期事件 ──────────────────────────────────────────
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

# ── 健康检查端点 ──────────────────────────────────────────
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


if __name__ == "__main__":
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)

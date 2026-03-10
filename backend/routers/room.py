"""
房间相关 API 路由

包含: 获取房间详情、创建/删除房间、刷新公开房间、加入/退出房间、准备状态
迁移自 main.py 第 935-1076 行
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from utils.logger_utils import get_logger
from dependencies import room_service
from config import MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["room"])


@router.get("/room/{invite_code}")
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

@router.post("/room/create_room")
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


@router.post("/room/{invite_code}/delete_room")
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

@router.get("/rooms/refresh_public_room")
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

@router.post("/room/{invite_code}/join_room")
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

@router.post("/room/{invite_code}/leave_room")
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

@router.post("/room/{invite_code}/ready")
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

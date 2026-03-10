"""
用户信息修改相关 API 路由

包含: 修改密码、修改头像、获取用户统计
迁移自 main.py 第 1133-1183 行 + 1285-1303 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict
from utils.logger_utils import get_logger
from dependencies import user_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["user"])


@router.post("/user/{user_id}/update_password")
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

@router.post("/user/{user_id}/update_avatar")
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

@router.get("/user/{user_id}/stats")
async def get_user_stats(user_id: str, request: Request):
    """获取用户统计数据"""
    try:
        # 验证当前用户是否有权限（仅允许用户查看自己的数据或管理员查看任何人的数据）
        current_user_id = request.state.user_id
        
        # 检查权限
        if current_user_id != user_id:
            user_info = await user_service.get_user_info(current_user_id)
            if not user_info["success"] or not user_info.get("data", {}).get("is_admin", False):
                return {"success": False, "message": "无权查看该用户的统计数据"}
        
        # 获取用户统计数据
        result = await user_service.get_user_stats(user_id)
        return result
    except Exception as e:
        logger.error(f"获取用户统计数据失败: {str(e)}")
        return {"success": False, "message": f"获取用户统计数据失败: {str(e)}"}

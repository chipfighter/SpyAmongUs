"""
反馈相关 API 路由

包含: 提交反馈、获取所有反馈(管理员)、更新反馈状态(管理员)
迁移自 main.py 第 1186-1283 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from utils.logger_utils import get_logger
from dependencies import feedback_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback/submit")
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

@router.get("/admin/feedbacks")
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

@router.post("/admin/feedback/{feedback_id}/update-status")
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

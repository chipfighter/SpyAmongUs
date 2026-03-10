"""
游戏相关 API 路由

包含: 提交投票
迁移自 main.py 第 1079-1130 行
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any
from utils.logger_utils import get_logger
from dependencies import game_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["game"])


@router.post("/room/{invite_code}/vote")
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

"""
管理员 API 路由

包含: 获取玩家列表、禁言、封禁、反馈管理(获取/标记已读/回复)
迁移自 main.py 第 1306-1749 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# TODO: 从 main.py 迁移以下端点:
# - GET  /api/admin/players                          (get_players)
# - POST /api/admin/mute                             (mute_player)
# - POST /api/admin/ban                              (ban_player)
# - GET  /api/admin/feedback                         (get_feedback)
# - PUT  /api/admin/feedback/{feedback_id}/read      (mark_feedback_read)
# - POST /api/admin/feedback/{feedback_id}/respond   (respond_to_feedback)

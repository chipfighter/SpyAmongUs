"""
反馈相关 API 路由

包含: 提交反馈、获取所有反馈(管理员)、更新反馈状态(管理员)
迁移自 main.py 第 1186-1283 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

# TODO: 从 main.py 迁移以下端点:
# - POST /api/feedback                       (submit_feedback)
# - GET  /api/admin/feedbacks                 (get_all_feedbacks)
# - PUT  /api/admin/feedback/{feedback_id}    (update_feedback_status)

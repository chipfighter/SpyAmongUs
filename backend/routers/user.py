"""
用户信息修改相关 API 路由

包含: 修改密码、修改头像、获取用户统计
迁移自 main.py 第 1133-1183 行 + 1285-1303 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["user"])

# TODO: 从 main.py 迁移以下端点:
# - PUT  /api/user/{user_id}/password    (update_password)
# - PUT  /api/user/{user_id}/avatar      (update_avatar)
# - GET  /api/user/{user_id}/stats       (get_user_stats)

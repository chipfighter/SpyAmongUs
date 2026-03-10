"""
认证相关 API 路由

包含: 注册、登录、登出、获取用户信息、刷新Token、轮换Token
迁移自 main.py 第 672-931 行
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])

# TODO: 从 main.py 迁移以下端点:
# - POST /api/register        (register)
# - POST /api/login            (login)
# - POST /api/logout           (logout)
# - GET  /api/user/{user_id}   (get_user_info)
# - POST /api/token/refresh    (refresh_token)
# - POST /api/token/rotate     (rotate_token)

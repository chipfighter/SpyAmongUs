"""
游戏相关 API 路由

包含: 提交投票
迁移自 main.py 第 1079-1130 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["game"])

# TODO: 从 main.py 迁移以下端点:
# - POST /api/rooms/{invite_code}/vote  (submit_vote)

"""
房间相关 API 路由

包含: 获取房间详情、创建/删除房间、刷新公开房间、加入/退出房间、准备状态
迁移自 main.py 第 935-1076 行
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["room"])

# TODO: 从 main.py 迁移以下端点:
# - GET    /api/room/{invite_code}          (get_room_details)
# - POST   /api/rooms                       (create_room)
# - DELETE /api/rooms/{invite_code}          (delete_room)
# - GET    /api/rooms/public                 (refresh_public_rooms)
# - POST   /api/rooms/{invite_code}/join     (join_room)
# - POST   /api/rooms/{invite_code}/leave    (leave_room)
# - POST   /api/rooms/{invite_code}/ready    (update_ready_status)

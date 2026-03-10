"""
WebSocket 端点路由

包含: WebSocket 连接管理、消息路由、心跳处理
迁移自 main.py 第 272-668 行
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.logger_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])

# TODO: 从 main.py 迁移以下端点:
# - WS /ws/{room_id}  (websocket_endpoint)

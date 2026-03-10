"""
WebSocket 端点路由

包含: WebSocket 连接管理、认证、消息路由
迁移自 main.py 第 272-668 行（分步迁移，本次为连接建立部分）
"""

import time
import json
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from utils.logger_utils import get_logger
from dependencies import (
    auth_service, user_service, room_service, 
    message_service, websocket_manager, redis_client
)
from config import (
    USER_STATUS_IN_ROOM, ROOM_KEY_PREFIX, 
    GAME_STATUS_PLAYING, ROOM_ALIVE_PLAYERS_KEY_PREFIX
)

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """websocket端口控制"""
    await websocket.accept()

    # 获取认证信息
    try:
        # 首先尝试从URL查询参数获取token
        token = websocket.query_params.get("token")
        
        # 如果URL中没有token，尝试从第一条消息获取
        if not token:
            data = await websocket.receive_json()
            token = data.get("token")
        
        # 1.验证是否获取到token
        if not token:
            logger.warning(f"WebSocket连接 {room_id} 缺少token")
            await websocket.close(code=1008, reason="Missing authentication")
            return
            
        # 验证token
        is_valid, payload = auth_service.verify_token(token, "access")

        if not is_valid or 'sub' not in payload:
            logger.warning(f"WebSocket连接 {room_id} 的token无效")
            await websocket.close(code=1008, reason="Invalid authentication")
            return

        user_id = payload['sub']
        
        logger.info(f"用户 {user_id} 尝试连接房间 {room_id} 的WebSocket")

        # 2.验证用户是否在指定房间
        user_info = await user_service.get_user_info(user_id)
        
        raw_user_data = await redis_client.get_user(user_id)
        logger.info(f"Redis中用户 {user_id} 的数据: {raw_user_data}")
        
        room_exists = await redis_client.check_room_exists(room_id)
        logger.info(f"房间 {room_id} 存在: {room_exists}")
        
        is_user_in_room_list = await redis_client.is_user_in_room(room_id, user_id)
        logger.info(f"用户 {user_id} 在房间 {room_id} 的用户列表中: {is_user_in_room_list}")
        
        current_room = user_info["data"].get("current_room") if user_info["success"] else "无法获取"
        logger.info(f"用户 {user_id} 的current_room字段值: {current_room}")
        
        user_status = user_info["data"].get("status") if user_info["success"] else "无法获取"
        logger.info(f"用户 {user_id} 的status字段值: {user_status}")
        
        if not room_exists:
            logger.warning(f"房间 {room_id} 不存在，拒绝WebSocket连接")
            await websocket.close(code=1008, reason="Room does not exist")
            return
            
        # 判断用户是否有权限连接该房间
        is_allowed = False
        
        if user_info["success"] and user_info["data"].get("current_room") == room_id:
            is_allowed = True
            logger.info(f"用户 {user_id} 的current_room字段匹配，允许连接")
            
        elif is_user_in_room_list:
            is_allowed = True
            logger.info(f"用户 {user_id} 在房间users集合中，允许连接，并自动修复状态")
            await user_service.update_current_room(user_id, room_id)
            await user_service.update_user_status(user_id, USER_STATUS_IN_ROOM)
            logger.info(f"已更新用户 {user_id} 的current_room为 {room_id}，状态为 {USER_STATUS_IN_ROOM}")
            
        if not is_allowed:
            logger.warning(f"用户 {user_id} 无权连接房间 {room_id} 的WebSocket")
            await websocket.close(code=1008, reason="User not in this room")
            return

        # 3.添加到连接管理器
        await websocket_manager.add_connection(room_id, user_id, websocket)
        logger.info(f"用户 {user_id} 已添加到房间 {room_id} 的WebSocket连接管理器")

        room_info = await room_service.get_room_basic_data(room_id)
        context = "join"
        room_name = "未知房间"
        if room_info and room_info.get("host_id") == user_id:
            context = "create"
        if room_info and room_info.get("room_name"):
            room_name = room_info["room_name"]
        logger.info(f"用户 {user_id} 连接房间 {room_id} 的上下文: {context}, 房间名: {room_name}")

        # 4.发送连接成功消息
        await websocket.send_json({
            "type": "system",
            "event": "connected",
            "room_id": room_id,
            "context": context,
            "room_name": room_name,
            "timestamp": int(time.time() * 1000)
        })
        logger.info(f"已向用户 {user_id} 发送WebSocket连接成功消息 (含上下文)")
        
        # 获取房间用户列表，并发送给客户端
        try:
            room_data = await room_service.get_room_data_users(room_id)
            if room_data["success"] and "room_data" in room_data["data"]:
                users_list = room_data["data"]["room_data"].get("users", [])
                await websocket.send_json({
                    "type": "user_list_update",
                    "users": users_list,
                    "timestamp": int(time.time() * 1000)
                })
                logger.info(f"已向用户 {user_id} 发送房间用户列表，共 {len(users_list)} 名用户")
        except Exception as e:
            logger.error(f"发送房间用户列表失败: {str(e)}")

        # 5.监听消息
        while True:
            try:
                raw_message = await websocket.receive_text()
                
                try:
                    message_data = json.loads(raw_message)
                    
                    await websocket_manager.update_connection_state(room_id, user_id)
                    logger.debug(f"用户 {user_id} 在房间 {room_id} 的活动时间已更新")
                    
                    # 调用消息处理函数
                    await _handle_ws_message(websocket, room_id, user_id, message_data)
                        
                except json.JSONDecodeError:
                    logger.error(f"收到无效JSON消息: {raw_message}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "消息格式无效",
                        "timestamp": int(time.time() * 1000)
                    })
                    
            except Exception as e:
                logger.error(f"处理WebSocket消息时出错: {str(e)}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"服务器处理消息时出错: {str(e)}",
                        "timestamp": int(time.time() * 1000)
                    })
                except:
                    break
                
                # 检查游戏状态并尝试恢复
                await _try_recover_game(room_id)

    except WebSocketDisconnect:
        try:
            if 'user_id' in locals() and 'room_id' in locals():
                await websocket_manager.remove_user_connection(room_id, user_id)
        except:
            pass
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
        try:
            await websocket.close(code=1011, reason="Server error")
        except:
            pass


async def _handle_ws_message(websocket: WebSocket, room_id: str, user_id: str, message_data: dict):
    """处理单条WebSocket消息 — TODO-14b 将填充完整逻辑"""
    # TODO: 下一轮 (TODO-14b) 将从 main.py 迁移完整的消息处理逻辑
    # 包含: ping/pong, god_role_response, god_words_selected, 
    #       god_words_selection_timeout, last_words, skip_last_words,
    #       vote, normal/secret messages
    pass


async def _try_recover_game(room_id: str):
    """尝试恢复游戏流程 — TODO-14b 将填充完整逻辑"""
    # TODO: 下一轮 (TODO-14b) 将从 main.py 迁移游戏恢复逻辑
    pass

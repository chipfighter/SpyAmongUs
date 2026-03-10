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
    """处理单条WebSocket消息，根据消息类型分发到对应处理逻辑"""
    
    # 处理心跳消息
    if message_data.get("type") == "ping":
        logger.debug(f"收到用户 {user_id} 的ping心跳，立即回复pong")
        await websocket.send_json({
            "type": "pong",
            "timestamp": int(time.time() * 1000)
        })
        return
    
    # 处理上帝角色回应消息
    if message_data.get("type") == "god_role_response":
        logger.info(f"处理上帝角色回应: {message_data}")
        await room_service.game_service.handle_god_response(user_id, message_data)
        return
    
    # 处理上帝选词消息
    if message_data.get("type") == "god_words_selected":
        logger.info(f"处理上帝选词: {message_data}")
        civilian_word = message_data.get("civilian_word", "")
        spy_word = message_data.get("spy_word", "")
        
        if not civilian_word or not spy_word:
            logger.error(f"词语数据不完整: civilian_word={civilian_word}, spy_word={spy_word}")
            await websocket.send_json({
                "type": "error",
                "message": "词语数据不完整",
                "timestamp": int(time.time() * 1000)
            })
            return
        
        # 广播消息给所有玩家，通知他们上帝已选词
        await websocket_manager.broadcast_message(
            room_id,
            {
                "type": "god_words_selected",
                "message": "上帝已选择词语，游戏正在初始化...",
                "timestamp": int(time.time() * 1000)
            },
            is_special=False
        )
        
        # 调用游戏服务的初始化方法
        await room_service.game_service.initialize_game(room_id, civilian_word, spy_word)
        return
    
    # 处理上帝选词超时消息
    if message_data.get("type") == "god_words_selection_timeout":
        logger.info(f"处理上帝选词超时: {message_data}")
        await websocket_manager.broadcast_message(
            room_id,
            {
                "type": "god_words_selection_timeout",
                "message": "上帝选词超时，由场外AI模拟上帝",
                "timestamp": int(time.time() * 1000)
            },
            is_special=False
        )
        return
    
    # 处理遗言消息
    if message_data.get("type") == "last_words":
        logger.info(f"处理玩家遗言: {message_data}")
        
        result = await room_service.game_service.handle_last_words(
            room_id=room_id,
            player_id=user_id,
            message=message_data
        )
        
        if not result.get("success", False):
            error_msg = result.get("message", "处理遗言失败")
            logger.error(f"遗言处理失败: {error_msg}")
            await websocket.send_json({
                "type": "error",
                "message": error_msg,
                "timestamp": int(time.time() * 1000)
            })
        return
    
    # 处理放弃遗言消息
    if message_data.get("type") == "skip_last_words":
        logger.info(f"玩家 {user_id} 放弃遗言")
        
        room_key = f"{ROOM_KEY_PREFIX}{room_id}"
        room_data = await redis_client.get_room_basic_data(room_id)
        last_words_player = room_data.get("last_words_player")
        
        if last_words_player != user_id:
            logger.warning(f"玩家 {user_id} 无权放弃遗言，当前遗言玩家为 {last_words_player}")
            await websocket.send_json({
                "type": "error",
                "message": "你没有权限放弃遗言",
                "timestamp": int(time.time() * 1000)
            })
            return
        
        # 广播玩家放弃遗言消息
        await websocket_manager.broadcast_message(
            room_id,
            {
                "type": "last_words_skipped",
                "player_id": user_id,
                "message": "玩家放弃遗言",
                "timestamp": int(time.time() * 1000)
            },
            is_special=False
        )
        
        # 清除遗言玩家信息
        await redis_client.hdel(room_key, "last_words_player")
        
        # 等待1.5秒，保持与正常遗言流程一致
        await asyncio.sleep(1.5)
        
        # 检查游戏是否结束
        game_end_result = await room_service.game_service.check_game_end_condition(room_id)
        
        if game_end_result["game_end"]:
            await room_service.game_service.broadcast_game_result(room_id, game_end_result)
        else:
            await room_service.game_service.start_next_round(room_id)
        return
    
    # 处理投票消息
    if message_data.get("type") == "vote":
        logger.info(f"收到玩家 {user_id} 的投票消息: {message_data}")
        
        target_id = message_data.get("target_id")
        if not target_id:
            logger.warning(f"玩家 {user_id} 发送的投票消息缺少target_id")
            await websocket.send_json({
                "type": "error",
                "message": "投票消息缺少目标玩家ID",
                "timestamp": int(time.time() * 1000)
            })
            return
        
        result = await room_service.game_service.handle_player_vote(
            room_id=room_id,
            voter_id=user_id,
            target_id=target_id
        )
        
        if not result.get("success", False):
            error_msg = result.get("message", "处理投票失败")
            logger.error(f"处理投票失败: {error_msg}")
            await websocket.send_json({
                "type": "error",
                "message": error_msg,
                "timestamp": int(time.time() * 1000)
            })
        return
    
    # 处理所有普通消息
    logger.info(f"收到WebSocket消息: {message_data}")
    
    if "room_id" not in message_data:
        message_data["room_id"] = room_id
    
    if "user_id" not in message_data:
        message_data["user_id"] = user_id
    
    # 根据消息类型处理
    if message_data.get("type") == "secret":
        logger.info("处理秘密消息")
        result = await message_service.process_secret_message(room_id, message_data, user_id)
    else:
        logger.info("处理普通消息")
        result = await message_service.process_message(message_data)
    
    logger.info(f"消息处理结果: {result}")
    
    if not result.get("success", False):
        error_msg = result.get("message", "处理消息失败")
        logger.error(f"消息处理失败: {error_msg}")
        await websocket.send_json({
            "type": "error",
            "message": error_msg,
            "timestamp": int(time.time() * 1000)
        })


async def _try_recover_game(room_id: str):
    """在消息处理异常时，尝试恢复游戏流程"""
    try:
        room_key = f"{ROOM_KEY_PREFIX}{room_id}"
        room_status = await redis_client.hget(room_key, "status")
        current_phase = await redis_client.hget(room_key, "current_phase")
        
        # 如果游戏正在进行中且处于发言阶段，尝试恢复游戏流程
        if room_status == GAME_STATUS_PLAYING and current_phase == "speaking":
            logger.warning(f"游戏正在进行中，尝试恢复发言流程: 房间={room_id}, 阶段={current_phase}")
            alive_players_key = ROOM_ALIVE_PLAYERS_KEY_PREFIX % room_id
            try:
                current_speaker = await redis_client.zrange(alive_players_key, 0, 0)
                if current_speaker and len(current_speaker) > 0 and current_speaker[0].startswith("llm_player_"):
                    logger.info(f"当前发言者是AI玩家 {current_speaker[0]}，尝试移动到下一个发言者")
                    await room_service.game_service.move_to_next_speaker(room_id)
            except Exception as recovery_error:
                logger.error(f"尝试恢复游戏流程失败: {str(recovery_error)}")
    except Exception as check_error:
        logger.error(f"检查游戏状态失败: {str(check_error)}")

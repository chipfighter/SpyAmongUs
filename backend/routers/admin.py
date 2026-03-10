"""
管理员 API 路由

包含: 获取玩家列表、禁言、封禁、反馈管理(获取/标记已读/回复)
迁移自 main.py 第 1306-1749 行
"""

import time
import json
import uuid
import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict
from utils.logger_utils import get_logger
from dependencies import user_service, mongo_client, redis_client, websocket_manager, room_service
from config import USER_STATUS_ONLINE, USER_STATUS_IN_ROOM

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/players")
async def get_players(request: Request):
    """获取所有玩家信息"""
    try:
        # 检查是否是管理员
        current_user = request.state.user_id
        user_info = await user_service.get_user_info(current_user)
        
        if not user_info["success"] or not user_info["data"].get("is_admin", False):
            logger.warning(f"用户 {current_user} 尝试访问管理员API但不具备管理员权限")
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "无权限访问"}
            )
        
        logger.info(f"管理员 {current_user} 正在获取玩家列表")
        
        try:
            # 从MongoDB查询所有用户
            users_collection = mongo_client.db.users
            logger.info("正在从MongoDB查询用户列表")
            players = await users_collection.find(
                {}, 
                {
                    "_id": 0,
                    "id": 1,
                    "username": 1,
                    "avatar_url": 1,
                    "status": 1,
                    "current_room": 1,
                    "last_login": 1,
                    "is_admin": 1,
                    "is_muted": 1,
                    "mute_until": 1,
                    "is_banned": 1,
                    "ban_until": 1
                }
            ).to_list(length=None)
            
            logger.info(f"从MongoDB获取到 {len(players)} 个用户")
            
            # 处理用户数据 - 确保房间状态信息正确
            for player in players:
                user_id = player["id"]
                
                # 检查用户是否在WebSocket连接管理器中
                is_connected = False
                for room_id, connections in websocket_manager.room_connections.items():
                    if user_id in connections:
                        is_connected = True
                        break
                
                # 如果用户在WebSocket连接中，说明在线
                if is_connected:
                    player["status"] = USER_STATUS_ONLINE
                    logger.info(f"用户 {user_id} 在WebSocket连接中，状态设为在线")
                # 如果用户有current_room，说明在房间中
                elif player.get("current_room"):
                    player["status"] = USER_STATUS_IN_ROOM
                    logger.info(f"用户 {user_id} 在房间中，状态设为在房间")
                # 如果Redis中有用户数据且状态为在线，说明在线
                else:
                    try:
                        redis_user_data = await redis_client.get_user(user_id)
                        if redis_user_data and redis_user_data.get("status") == USER_STATUS_ONLINE:
                            player["status"] = USER_STATUS_ONLINE
                            logger.info(f"用户 {user_id} 在Redis中显示为在线")
                        else:
                            player["status"] = "offline"
                            logger.info(f"用户 {user_id} 不在线")
                    except Exception as redis_error:
                        logger.error(f"获取Redis用户状态错误: {str(redis_error)}")
                        player["status"] = "offline"
                
                # 确保时间戳是可序列化的
                if "last_login" in player and isinstance(player["last_login"], datetime.datetime):
                    player["last_login"] = int(player["last_login"].timestamp())
            
            # 统计在线玩家数量
            online_count = sum(1 for p in players if p.get("status") == USER_STATUS_ONLINE)
            logger.info(f"当前在线玩家数量: {online_count}")
            
            # 缓存到Redis，设置30秒过期时间
            redis_key = "online_players_list"
            await redis_client.set_with_expiry(redis_key, json.dumps(players, default=str), 30)
            
            return {"success": True, "data": players}
        except Exception as e:
            logger.error(f"获取玩家列表错误: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "获取玩家列表失败"}
            )
    except Exception as e:
        logger.error(f"管理员API错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"服务器错误: {str(e)}"}
        )

@router.post("/mute")
async def mute_player(request: Request):
    """禁言玩家"""
    try:
        # 检查是否是管理员
        current_user = request.state.user_id
        user_info = await user_service.get_user_info(current_user)
        
        if not user_info["success"] or not user_info["data"].get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "无权限访问"}
            )
        
        # 处理请求数据
        data = await request.json()
        user_id = data.get('user_id')
        duration = data.get('duration', 3600)  # 默认1小时
        
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "缺少用户ID"}
            )
        
        # 设置禁言
        mute_until = int(time.time()) + duration
        
        # 更新MongoDB中的用户数据
        users_collection = mongo_client.db.users
        result = await users_collection.update_one(
            {"id": user_id},
            {"$set": {"is_muted": True, "mute_until": mute_until}}
        )
        
        if result.modified_count == 0:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "用户不存在或禁言设置失败"}
            )
        
        # 发送WebSocket通知给被禁言的用户
        user_to_mute = await users_collection.find_one({"id": user_id})
        if user_to_mute:
            notification = {
                "type": "system_notification",
                "message": f"您已被管理员禁言，禁言将持续 {duration // 3600} 小时",
                "level": "warning",
                "timestamp": int(time.time() * 1000)
            }
            
            # 发送消息给用户，如果用户在线
            await websocket_manager.send_personal_message(user_id, notification)
        
        # 同时更新Redis中的用户数据
        await redis_client.update_user_field(user_id, "is_muted", True)
        await redis_client.update_user_field(user_id, "mute_until", mute_until)
        
        return {"success": True, "message": "禁言设置成功"}
    except Exception as e:
        logger.error(f"禁言玩家错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"禁言玩家失败: {str(e)}"}
        )

@router.post("/ban")
async def ban_player(request: Request):
    """封禁玩家"""
    try:
        # 检查是否是管理员
        current_user = request.state.user_id
        user_info = await user_service.get_user_info(current_user)
        
        if not user_info["success"] or not user_info["data"].get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "无权限访问"}
            )
        
        # 处理请求数据
        data = await request.json()
        user_id = data.get('user_id')
        duration = data.get('duration', 86400)  # 默认1天
        
        if not user_id:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "缺少用户ID"}
            )
        
        # 设置封禁
        ban_until = int(time.time()) + duration
        
        # 更新MongoDB中的用户数据
        users_collection = mongo_client.db.users
        result = await users_collection.update_one(
            {"id": user_id},
            {"$set": {"is_banned": True, "ban_until": ban_until}}
        )
        
        if result.modified_count == 0:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "用户不存在或封禁设置失败"}
            )
        
        # 发送WebSocket通知给被封禁的用户
        user_to_ban = await users_collection.find_one({"id": user_id})
        if user_to_ban:
            notification = {
                "type": "system_notification",
                "message": f"您已被管理员封禁，封禁将持续 {duration // 86400} 天",
                "level": "error",
                "timestamp": int(time.time() * 1000)
            }
            
            # 发送消息给用户，如果用户在线
            await websocket_manager.send_personal_message(user_id, notification)
            
            # 如果用户在游戏中，强制踢出
            if user_to_ban.get("current_room"):
                room_id = user_to_ban.get("current_room")
                
                # 通知房间内其他玩家
                leave_room_data = {
                    "type": "player_left",
                    "user_id": user_id,
                    "username": user_to_ban.get("username"),
                    "reason": "banned",
                    "timestamp": int(time.time() * 1000)
                }
                
                await websocket_manager.broadcast_message(room_id, leave_room_data)
                
                # 更新用户状态
                await users_collection.update_one(
                    {"id": user_id},
                    {"$set": {"current_room": None, "status": "offline"}}
                )
                
                # 同时更新Redis中的用户数据
                await redis_client.update_user_field(user_id, "current_room", None)
                await redis_client.update_user_field(user_id, "status", "offline")
                
                # 从房间用户列表中移除该用户
                await room_service.remove_user_from_room(room_id, user_id)
        
        # 更新Redis中的用户数据
        await redis_client.update_user_field(user_id, "is_banned", True)
        await redis_client.update_user_field(user_id, "ban_until", ban_until)
        
        return {"success": True, "message": "封禁设置成功"}
    except Exception as e:
        logger.error(f"封禁玩家错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"封禁玩家失败: {str(e)}"}
        )

@router.get("/feedback")
async def get_feedback(request: Request):
    """获取所有反馈信息"""
    try:
        # 检查是否是管理员
        current_user = request.state.user_id
        user_info = await user_service.get_user_info(current_user)
        
        if not user_info["success"] or not user_info["data"].get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "无权限访问"}
            )
        
        # 从MongoDB获取反馈信息
        feedback_collection = mongo_client.db.feedbacks
        feedback_cursor = feedback_collection.find({}).sort("created_at", -1)
        feedback_list = await feedback_cursor.to_list(length=None)
        
        # 处理MongoDB文档：移除_id字段，转换时间戳，添加用户信息
        processed_feedback = []
        users_collection = mongo_client.db.users
        
        for item in feedback_list:
            # 处理_id字段
            if "_id" in item:
                item_dict = dict(item)
                del item_dict["_id"]
            else:
                item_dict = dict(item)
            
            # 转换时间戳
            if "created_at" in item_dict:
                if isinstance(item_dict["created_at"], datetime.datetime):
                    # 如果是datetime类型，转换为时间戳
                    item_dict["created_at"] = int(item_dict["created_at"].timestamp())
                elif not isinstance(item_dict["created_at"], (int, float)):
                    # 如果不是时间戳类型，转换为当前时间戳
                    item_dict["created_at"] = int(time.time())
            
            # 添加用户信息
            if "user_id" in item_dict and item_dict["user_id"]:
                try:
                    user = await users_collection.find_one({"id": item_dict["user_id"]})
                    if user:
                        item_dict["username"] = user.get("username", "未知用户")
                        item_dict["user_avatar"] = user.get("avatar_url", "")
                    else:
                        item_dict["username"] = "未知用户"
                        item_dict["user_avatar"] = ""
                except Exception:
                    item_dict["username"] = "未知用户"
                    item_dict["user_avatar"] = ""
            
            processed_feedback.append(item_dict)
        
        return {"success": True, "data": processed_feedback}
    except Exception as e:
        logger.error(f"获取反馈信息错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"获取反馈信息失败: {str(e)}"}
        )

@router.post("/feedback/{feedback_id}/read")
async def mark_feedback_read(feedback_id: str, request: Request):
    """标记反馈为已读"""
    try:
        # 检查是否是管理员
        current_user = request.state.user_id
        user_info = await user_service.get_user_info(current_user)
        
        if not user_info["success"] or not user_info["data"].get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "无权限访问"}
            )
        
        # 更新反馈状态
        feedback_collection = mongo_client.db.feedbacks
        current_timestamp = int(time.time())  # 使用时间戳
        result = await feedback_collection.update_one(
            {"id": feedback_id},
            {"$set": {
                "read": True,
                "read_by": current_user,
                "read_at": current_timestamp
            }}
        )
        
        if result.modified_count == 0:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "反馈不存在或已标记为已读"}
            )
        
        return {"success": True, "message": "已标记为已读"}
    except Exception as e:
        logger.error(f"标记反馈已读错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"标记反馈已读失败: {str(e)}"}
        )

@router.post("/feedback/{feedback_id}/respond")
async def respond_to_feedback(feedback_id: str, request: Request):
    """回复反馈"""
    try:
        # 检查是否是管理员
        current_user = request.state.user_id
        user_info = await user_service.get_user_info(current_user)
        
        if not user_info["success"] or not user_info["data"].get("is_admin", False):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "无权限访问"}
            )
        
        # 处理请求数据
        data = await request.json()
        message = data.get('message')
        
        if not message:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "回复内容不能为空"}
            )
        
        # 获取反馈信息
        feedback_collection = mongo_client.db.feedbacks
        feedback = await feedback_collection.find_one({"id": feedback_id})
        
        if not feedback:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "反馈不存在"}
            )
        
        # 创建回复记录
        current_timestamp = int(time.time())  # 使用时间戳
        response_data = {
            "id": str(uuid.uuid4()),
            "feedback_id": feedback_id,
            "admin_id": current_user,
            "admin_name": user_info["data"]["username"],
            "message": message,
            "created_at": current_timestamp
        }
        
        # 存储回复
        feedback_responses_collection = mongo_client.db.feedback_responses
        await feedback_responses_collection.insert_one(response_data)
        
        # 更新原反馈状态
        await feedback_collection.update_one(
            {"id": feedback_id},
            {"$set": {
                "read": True,
                "responded": True,
                "responded_by": current_user,
                "responded_at": current_timestamp
            }}
        )
        
        # 如果反馈有用户信息，发送通知给用户
        if "user_id" in feedback and feedback["user_id"]:
            notification = {
                "type": "feedback_response",
                "feedback_id": feedback_id,
                "feedback_title": feedback.get("title", "您的反馈"),
                "message": f"管理员已回复您的反馈: {message}",
                "timestamp": int(time.time() * 1000)
            }
            
            await websocket_manager.send_personal_message(feedback["user_id"], notification)
        
        return {"success": True, "message": "回复已发送"}
    except Exception as e:
        logger.error(f"回复反馈错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"回复反馈失败: {str(e)}"}
        )

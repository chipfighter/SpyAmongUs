"""
services: room_service

Description:
    实现一切和房间直接相关的业务逻辑操作

Notes:
    返回格式统一:
    Dict[str, Any]，包含以下字段：
    - success: bool，操作是否成功
    - message: str，操作结果消息
    - data: Optional[Dict]，返回的数据（如果有）

    - 创建、删除房间
    - 获取公开房间列表

To-Do:
    - 删除用户（需要判断是否房主+是否处于游戏中）
"""

from typing import Dict, Any, Optional
from models.room import Room
from services.user_service import UserService
from utils.redis_utils import RedisClient
from utils.logger_utils import get_logger
from utils.websocket_manager import WebSocketManager
from config import (
    MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME, USER_STATUS_ONLINE, USER_STATUS_IN_ROOM
)
import asyncio

logger = get_logger(__name__)

class RoomService:
    def __init__(self, user_service: UserService, redis_client: RedisClient, websocket_manager: Optional[WebSocketManager] = None):
        self.user_service = user_service
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        # 初始化message_service为None，稍后设置
        self.message_service = None
        logger.info("房间服务已初始化")

    def set_message_service(self, message_service):
        """设置消息服务，避免循环依赖"""
        self.message_service = message_service

    async def create_room(self, room_name: str, host_id: str, is_public: bool = True,
                          total_players: int = MIN_PLAYERS, spy_count: int = MIN_SPY_COUNT,
                          max_rounds: int = MAX_ROUNDS, speak_time: int = MAX_SPEAK_TIME,
                          last_words_time: int = MAX_LAST_WORDS_TIME, llm_free: bool = False) -> Dict[str, Any]:
        """
        创建新房间

        Args:
            room_name: 房间名称
            host_id: 房主ID
            is_public: 是否公开
            total_players: 总玩家数
            spy_count: 卧底数量
            max_rounds: 最大回合数
            speak_time: 发言时间（秒）
            last_words_time: 遗言时间（秒）
            llm_free: 是否允许大模型自由聊天

        Returns:
            Dict包含操作结果

        Notes:
            实例化room对象，然后将其写入redis缓存，然后更改房主的个人信息
        """
        try:
            # 检查host_id是否有效
            user_info = await self.user_service.get_user_info(host_id)
            if not user_info["success"]:
                return {
                    "success": False,
                    "message": "找不到该用户，无法创建房间"
                }

            # 检查用户是否已在其他房间
            user_data = user_info["data"]
            if user_data.get("current_room"):
                return {
                    "success": False,
                    "message": "您已在其他房间中，请先退出当前房间"
                }

            # 创建Room对象
            room = Room.create_room(room_name=room_name, host_id=host_id, is_public=is_public, total_players=total_players,
                                    spy_count=spy_count, max_rounds=max_rounds, speak_time=speak_time,
                                    last_words_time=last_words_time, llm_free=llm_free)

            # 房主就是唯一的用户
            room.users = {host_id}

            # 准备Redis缓存数据
            room_dict = room.dict()

            # 缓存房间数据到Redis
            success = await self.redis_client.cache_room(room.invite_code, room_dict)

            if success:
                # 更新房主当前房间
                await self.user_service.update_current_room(host_id, room.invite_code)

                # 更新房主状态为在房间中
                await self.user_service.update_user_status(host_id, USER_STATUS_IN_ROOM)
                
                # 创建房间成功后发送系统通知
                if self.message_service:
                    await self.message_service.send_system_message(
                        room_id=room.invite_code,
                        content=f"房间 \"{room_name}\" 已创建，等待其他玩家加入..."
                    )

                return {
                    "success": True,
                    "message": "房间创建成功",
                    "data": {
                        "invite_code": room.invite_code,
                        "room_data": room_dict
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "创建房间失败，请稍后重试"
                }

        except Exception as e:
            logger.error(f"创建房间时发生错误: {str(e)}")
            return {
                "success": False,
                "message": f"创建房间失败: {str(e)}"
            }

    async def delete_room(self, invite_code: str, operator_id: str = None, 
                          notify_users: bool = True, reason: str = "房间已关闭") -> Dict[str, Any]:
        """
        删除房间

        Args:
            invite_code: 房间邀请码
            operator_id: 操作者ID（如果是房主手动删除，需要检查权限）
            notify_users: 是否通知房间内的用户
            reason: 关闭房间的原因

        Returns:
            Dict包含操作结果
        """
        try:
            # 如果指定了操作者，检查是否是房主
            if operator_id:
                # 检查房间是否存在
                room_exists = await self.redis_client.check_room_exists(invite_code)
                if not room_exists:
                    return {
                        "success": False,
                        "message": "房间不存在"
                    }
                
                # 获取房间数据
                room_data = await self.redis_client.get_room_basic_data(invite_code)
                if not room_data:
                    return {
                        "success": False,
                        "message": "房间不存在"
                    }

                if room_data.get("host_id") != operator_id:
                    return {
                        "success": False,
                        "message": "只有房主才能删除房间"
                    }

            # 获取房间中的所有用户
            users = await self.redis_client.get_room_users(invite_code)
            
            # 如果启用了通知且消息服务可用
            if notify_users and self.message_service:
                try:
                    # 发送系统消息通知房间即将关闭
                    await self.message_service.send_system_message(
                        room_id=invite_code,
                        content=f"房间即将关闭: {reason}"
                    )

                    # 给用户一点时间接收消息
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.error(f"发送房间关闭通知失败: {str(e)}")
            
            # 如果WebSocket管理器可用，关闭所有连接
            if notify_users and self.websocket_manager:
                try:
                    # 关闭所有WebSocket连接
                    await self.websocket_manager.close_room_connections(invite_code, list(users))
                except Exception as e:
                    logger.error(f"关闭WebSocket连接失败: {str(e)}")
            
            # 更新所有用户的状态和当前房间
            for user_id in users:
                # 修改用户状态从in_room变为online
                await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
                # 清除用户当前房间
                await self.user_service.update_current_room(user_id, None)

            # 删除Redis中的房间数据
            success = await self.redis_client.delete_room(invite_code)

            if success:
                return {
                    "success": True,
                    "message": "房间已删除",
                    "data": {
                        "reason": reason
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "删除房间失败，请稍后重试"
                }

        except Exception as e:
            logger.error(f"删除房间时发生错误: {str(e)}")
            return {
                "success": False,
                "message": f"删除房间失败: {str(e)}"
            }

    async def get_public_rooms(self) -> Dict[str, Any]:
        """
        获取所有公开房间列表

        Returns:
            Dict: 包含操作结果和房间列表
        """
        try:
            # 从Redis获取公开房间列表
            rooms = await self.redis_client.get_public_rooms()

            # 按照房间创建时间排序（降序，最新的房间在前面）
            if rooms:
                rooms.sort(key=lambda x: int(x.get("created_at", 0)), reverse=True)

            return {
                "success": True,
                "message": "获取公开房间列表成功",
                "data": {
                    "rooms": rooms
                }
            }
        except Exception as e:
            logger.error(f"获取公开房间列表失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取公开房间列表失败: {str(e)}"
            }
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

Methods:
    - 创建、删除房间、加入、退出房间
    - 获取公开房间列表、获取房间基本信息（不包含用户列表）、获取房间详细信息（包含用户列表）
    - 用户的准备/取消准备
"""
import time
from typing import Dict, Any, Optional, Set
from models.room import Room
from services.user_service import UserService
from utils.redis_utils import RedisClient
from utils.logger_utils import get_logger
from utils.websocket_manager import WebSocketManager
from services.game_service import GameService
from config import (
    MIN_PLAYERS, MIN_SPY_COUNT, MAX_ROUNDS, MAX_SPEAK_TIME, MAX_LAST_WORDS_TIME, USER_STATUS_ONLINE,
    USER_STATUS_IN_ROOM, GAME_STATUS_WAITING, ROOM_POLL_STATE_KEY_PREFIX
)
import asyncio
from pydantic import ValidationError
import json 

logger = get_logger(__name__)

class RoomService:
    def __init__(self, user_service: UserService, redis_client: RedisClient, websocket_manager: Optional[WebSocketManager] = None):
        self.user_service = user_service
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        self.message_service = None
        self.countdown_tasks = {}  # 房间ID -> asyncio任务的映射
                
        # 获取用户服务的mongo_client
        mongo_client = getattr(user_service, "mongo_client", None)
                
        # 初始化GameService，传递mongo_client
        self.game_service = GameService(self.redis_client, self.websocket_manager, mongo_client)
                
        # 设置用户服务，解决循环依赖
        self.game_service.set_user_service(user_service)
        
        if redis_client and websocket_manager:
            logger.info("RoomService已初始化")

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
                    
                # 构建房主的用户信息，用于广播用户列表
                if self.websocket_manager:
                    try:
                        # 获取新创建房间的房主信息
                        host_user = {
                            "id": host_id,
                            "username": user_data.get("username", "房主"),
                            "avatar_url": user_data.get("avatar_url", "/default_avatar.jpg"),
                            "status": USER_STATUS_IN_ROOM
                        }
                        
                        # 广播用户列表更新（此时只有房主一人）
                        await self.websocket_manager.broadcast_message(
                            invite_code=room.invite_code,
                            message={
                                "type": "user_list_update",
                                "users": [host_user],
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        logger.info(f"已向房间 {room.invite_code} 广播初始用户列表（房主）")
                    except Exception as e:
                        logger.error(f"广播房主信息失败: {str(e)}")

                return {
                    "success": True,
                    "message": "房间创建成功",
                    "data": {
                        "invite_code": room.invite_code
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
                raw_room_data = await self.redis_client.get_room_basic_data(invite_code)
                if not raw_room_data:
                    logger.error(f"删除房间 {invite_code} 失败：无法获取房间数据")
                    return {"success": False, "message": "房间不存在或数据错误"}
                
                try:
                    room: Room = Room.model_validate(raw_room_data)
                except ValidationError as e:
                    logger.error(f"房间 {invite_code} 数据校验失败: {e}")
                    return {"success": False, "message": "房间配置错误"}

                # 使用验证后的 room.host_id
                if room.host_id != operator_id:
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

            # 删除轮询状态
            await self.redis_client.delete_poll_state(invite_code)
            logger.info(f"已清理房间 {invite_code} 的轮询状态")

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

    async def join_room(self, invite_code: str, user_id: str) -> Dict[str, Any]:
        """
        加入房间

        Args:
            invite_code: 房间邀请码
            user_id: 用户ID

        Returns:
            Dict包含操作结果
        """
        try:
            # 1. 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(invite_code)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }

            # 2. 检查用户是否已在其他房间
            user_info = await self.user_service.get_user_info(user_id)
            if not user_info["success"]:
                return {
                    "success": False,
                    "message": "用户信息获取失败"
                }

            if user_info["data"].get("current_room"):
                # 检查是否正好就是当前要加入的房间
                if user_info["data"].get("current_room") == invite_code:
                    return {
                        "success": True,
                        "message": "您已在该房间中"
                    }
                else:
                    return {
                        "success": False,
                        "message": "您已在其他房间中，请先退出当前房间"
                    }

            # 3. 检查房间是否已满
            raw_room_data = await self.redis_client.get_room_basic_data(invite_code)
            if not raw_room_data:
                logger.error(f"加入房间 {invite_code} 失败：无法获取房间数据")
                return {"success": False, "message": "房间数据错误"}

            # 校验房间数据
            try:
                room: Room = Room.model_validate(raw_room_data)
            except ValidationError as e:
                logger.error(f"房间 {invite_code} 数据校验失败: {e}")
                return {"success": False, "message": "房间配置错误"}
                
            current_users_count = await self.redis_client.get_room_users_count(invite_code)
            # 使用验证后的 room.total_players (int 类型)
            if current_users_count >= room.total_players:
                return {
                    "success": False,
                    "message": "房间已满"
                }

            # 4. 将用户添加到房间（更新房间的redis缓存）
            success = await self.redis_client.update_room_user(invite_code, user_id)
            if not success:
                return {
                    "success": False,
                    "message": "加入房间失败"
                }

            # 5. 更新用户redis状态
            await self.user_service.update_current_room(user_id, invite_code)
            await self.user_service.update_user_status(user_id, USER_STATUS_IN_ROOM)
            # 6. 广播用户加入消息给所有用户（仅仅广播新用户的info）
            if self.websocket_manager:
                username = user_info["data"].get("username")
                avatar_url = user_info["data"].get("avatar_url")

                await self.websocket_manager.broadcast_message(
                    invite_code=invite_code, 
                    message={
                        "type": "user_join",
                        "user_id": user_id,
                        "username": username,
                        "avatar_url": avatar_url,
                        "content": f"用户 {username} 加入了房间",
                        "timestamp": int(time.time() * 1000),
                    },
                    is_special=False, 
                    target_users=None
                )
                
                # 7. 获取并广播最新的用户列表给所有人
                try:
                    room_data = await self.get_room_data_users(invite_code)
                    if room_data["success"] and "room_data" in room_data["data"]:
                        users_list = room_data["data"]["room_data"].get("users", [])
                        # 广播user_list_update消息给房间内所有用户
                        await self.websocket_manager.broadcast_message(
                            invite_code=invite_code,
                            message={
                                "type": "user_list_update",
                                "users": users_list,
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        logger.info(f"已向房间 {invite_code} 的所有用户广播最新用户列表，共 {len(users_list)} 名用户")
                except Exception as e:
                    logger.error(f"广播用户列表失败: {str(e)}")

            return {
                "success": True,
                "message": "成功加入房间"
            }

        except Exception as e:
            logger.error(f"加入房间失败: {str(e)}")
            return {
                "success": False,
                "message": f"加入房间失败: {str(e)}"
            }

    async def leave_room(self, invite_code: str, user_id: str) -> Dict[str, Any]:
        """
        退出房间

        Args:
            invite_code: 房间邀请码
            user_id: 用户ID

        Returns:
            Dict包含操作结果
        """
        try:
            user_info = await self.user_service.get_user_info(user_id)
            
            # 1. 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(invite_code)
            if not room_exists:
                # 如果房间不存在，也可能用户状态未清理，尝试清理用户状态
                await self.user_service.update_current_room(user_id, None)
                await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
                return {
                    "success": False,
                    "message": "房间不存在"
                }

            # 2. 检查用户是否在房间中
            is_in_room = await self.redis_client.is_user_in_room(invite_code, user_id)
            if not is_in_room:
                # 直接用 try 最前面获取的 user_info
                if user_info["success"] and user_info["data"].get("current_room") == invite_code:
                    await self.user_service.update_current_room(user_id, None)
                    await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
                return {
                    "success": False,
                    "message": "您不在该房间中"
                }

            # 3. 获取房间数据
            raw_room_data = await self.redis_client.get_room_basic_data(invite_code)
            if not raw_room_data:
                logger.error(f"退出房间 {invite_code} 失败：无法获取房间数据")
                # 即使获取房间数据失败，也要尝试清理用户状态
                await self.user_service.update_current_room(user_id, None)
                await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
                return {"success": False, "message": "房间数据错误"}
            
            try:
                room: Room = Room.model_validate(raw_room_data)
            except ValidationError as e:
                logger.error(f"房间 {invite_code} 数据校验失败: {e}")
                return {"success": False, "message": "房间配置错误"}

            # 4. 如果是房主，需要特殊处理
            is_leaving_host = (room.host_id == user_id)
            next_host_id = None # 初始化下一任房主ID
            new_host_name = "新房主"
            former_host_name = "前房主"
            
            if is_leaving_host:
                # 获取房间中的所有其他用户
                all_users = await self.redis_client.get_room_users(invite_code)
                other_users = [u for u in all_users if u != user_id]

                # 如果没有其他用户，直接删除房间
                if not other_users:
                    # 房主是最后一人退出房间，将删除房间
                    # 清理房主状态并删除房间
                    await self.user_service.update_current_room(user_id, None)
                    await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
                    
                    # 从准备用户集合中移除该用户
                    await self.redis_client.remove_user_from_ready_set(invite_code, user_id)
                    
                    # 调用 delete_room，但不通知用户，因为已经没人了
                    return await self.delete_room(invite_code, operator_id=user_id, notify_users=False, reason="房主退出且房间为空")

                # 有其他用户，需要转移房主权限
                next_host_id = await self.redis_client.get_next_user_by_join_time(invite_code, user_id)

                if not next_host_id or next_host_id == user_id:
                    # 如果无法确定下一个房主，使用第一个其他用户
                    if other_users:
                         next_host_id = other_users[0]
                    else: # 理论上不会到这里，因为前面已经处理了空房间情况
                         logger.error(f"尝试转移房主权限但在房间 {invite_code} 找不到其他用户")
                         # 同样删除房间
                         await self.user_service.update_current_room(user_id, None)
                         await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
                         
                         # 从准备用户集合中移除该用户
                         await self.redis_client.remove_user_from_ready_set(invite_code, user_id)
                         
                         return await self.delete_room(invite_code, operator_id=user_id, notify_users=False, reason="转移房主失败，房间关闭")

                # 更新房间的房主信息
                room.host_id = next_host_id
                await self.redis_client.update_room_host(invite_code, next_host_id)
                
                # 获取新旧房主的用户名（用于通知消息）
                user_leaving_name = user_info["data"].get("username", "前房主") if user_info["success"] else former_host_name
                
                next_host_info = await self.user_service.get_user_info(next_host_id)
                next_host_name = next_host_info["data"].get("username", "新房主") if next_host_info["success"] else new_host_name
                
                # 广播房主变更消息
                if self.websocket_manager:
                    await self.websocket_manager.broadcast_message(
                        invite_code=invite_code,
                        message={
                            "type": "host_leave",
                            "user_id": user_id,
                            "new_host_id": next_host_id,
                            "content": f"前房主 {user_leaving_name} 离开了房间，{next_host_name} 成为新房主",
                            "timestamp": int(time.time() * 1000)
                        },
                        is_special=False
                    )
            else:
                # 普通用户离开
                # 获取离开用户的用户名
                user_leaving_name = user_info["data"].get("username", "某用户") if user_info["success"] else "某用户"
                
                # 广播用户离开消息
                if self.websocket_manager:
                    await self.websocket_manager.broadcast_message(
                        invite_code=invite_code,
                        message={
                            "type": "user_leave",
                            "user_id": user_id,
                            "content": f"用户 {user_leaving_name} 离开了房间",
                            "timestamp": int(time.time() * 1000)
                        },
                        is_special=False
                    )
            
            # 清理用户状态
            await self.user_service.update_current_room(user_id, None)
            await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
            
            # 从准备用户集合中移除该用户
            await self.redis_client.remove_user_from_ready_set(invite_code, user_id)
            
            # 从房间用户集合中移除该用户
            await self.redis_client.delete_room_user(invite_code, user_id)
            
            # 广播更新后的用户列表
            if self.websocket_manager:
                try:
                    # 获取最新的用户列表
                    room_data = await self.get_room_data_users(invite_code)
                    if room_data["success"] and "room_data" in room_data["data"]:
                        users_list = room_data["data"]["room_data"].get("users", [])
                        # 广播user_list_update消息
                        await self.websocket_manager.broadcast_message(
                            invite_code=invite_code,
                            message={
                                "type": "user_list_update",
                                "users": users_list,
                                "timestamp": int(time.time() * 1000)
                            },
                            is_special=False
                        )
                        logger.info(f"用户离开后广播更新用户列表，共 {len(users_list)} 名用户")
                except Exception as e:
                    logger.error(f"广播更新用户列表失败: {str(e)}")
            
            return {
                "success": True,
                "message": "已退出房间"
            }

        except Exception as e:
            logger.error(f"退出房间失败: {str(e)}", exc_info=True)
             # 出现异常时，也尝试清理用户状态
            try:
                await self.user_service.update_current_room(user_id, None)
                await self.user_service.update_user_status(user_id, USER_STATUS_ONLINE)
            except Exception as cleanup_e:
                 logger.error(f"退出房间异常处理中清理用户 {user_id} 状态失败: {cleanup_e}")
            return {
                "success": False,
                "message": f"退出房间失败: {str(e)}"
            }

    async def get_public_rooms(self) -> Dict[str, Any]:
        """
        获取所有公开房间列表, 包含聚合信息

        Returns:
            Dict: 包含操作结果和聚合后的房间列表
                  每个房间对象将额外包含:
                  - current_players: int, 当前房间人数
                  - host_avatar_url: Optional[str], 房主头像URL
                  - host_username: Optional[str], 房主用户名
        """
        try:
            public_room_codes = await self.redis_client.get_public_rooms()
            
            if not public_room_codes:
                return {
                    "success": True,
                    "message": "没有公开房间",
                    "data": {"rooms": []}
                }

            augmented_rooms = []
            for invite_code in public_room_codes:
                try:
                    # 获取原始房间数据 (字典，值为字符串)
                    raw_room_data = await self.redis_client.get_room_basic_data(invite_code)
                    if not raw_room_data:
                        logger.warning(f"无法获取房间 {invite_code} 的基本数据，跳过")
                        continue
                    
                    # 使用 Pydantic 进行解析和类型转换
                    try:
                        # 假设使用 Pydantic V2 的 model_validate
                        # 如果是 V1，使用 room: Room = Room.parse_obj(raw_room_data)
                        room: Room = Room.model_validate(raw_room_data)
                    except ValidationError as e:
                        logger.error(f"房间 {invite_code} 数据校验或转换失败: {e}, data: {raw_room_data}")
                        continue # 跳过这个格式错误的房间
                        
                    # 获取房主ID (现在 room.host_id 类型是 str)
                    host_id = room.host_id 
                    host_avatar_url = None
                    host_username = None
                    
                    # 获取房主信息
                    if host_id:
                        # 直接获取user_info或者拿着id去用户hash获取
                        user_info_result = await self.user_service.get_user_info(host_id)
                        if user_info_result["success"] and user_info_result.get("data"):
                           host_avatar_url = user_info_result["data"].get("avatar_url")
                           host_username = user_info_result["data"].get("username")
                        else:
                           host_user_data = await self.redis_client.get_user(host_id)
                           host_avatar_url = host_user_data.get("avatar_url")
                           host_username = host_user_data.get("username")

                    # 获取当前玩家数量
                    current_players = await self.redis_client.get_room_users_count(invite_code)

                    # 准备返回给前端的数据 (基于验证过的 Room 对象)
                    room_output_dict = room.dict() # 使用 Pydantic 的 .dict() 获取字典
                    room_output_dict["current_players"] = current_players
                    room_output_dict["host_avatar_url"] = host_avatar_url or ""
                    room_output_dict["host_username"] = host_username or ""

                    augmented_rooms.append(room_output_dict)
                    
                except Exception as inner_e:
                     logger.error(f"处理房间 {invite_code} 时出错: {str(inner_e)}", exc_info=True)
                     continue

            # 按照房间创建时间排序
            if augmented_rooms:
                augmented_rooms.sort(key=lambda x: x.get("created_at", 0), reverse=True)

            return {
                "success": True,
                "message": "获取公开房间列表成功",
                "data": {
                    "rooms": augmented_rooms
                }
            }
        except Exception as e:
            logger.error(f"获取公开房间列表失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"获取公开房间列表失败: {str(e)}"
            }
            
    async def get_room_basic_data(self, invite_code: str) -> Optional[Dict[str, Any]]:
        """获取房间的基础信息 (不包含用户列表)"""
        try:
            # 直接调用 Redis 工具类的方法
            room_data = await self.redis_client.get_room_basic_data(invite_code)
            if not room_data:
                logger.warning(f"无法从 Redis 获取房间 {invite_code} 的基础数据")
                return None

            return room_data
        except Exception as e:
            logger.error(f"获取房间 {invite_code} 基础数据时出错: {str(e)}")
            return None

    async def get_room_data_users(self, invite_code: str) -> Dict[str, Any]:
        """
        获取指定房间的详细信息

        Notes:
            获取房间基础数据+用户列表数据
        """
        try:
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(invite_code)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
                
            # 从Redis获取房间的完整数据
            room_data = await self.redis_client.get_room_basic_data(invite_code) 
            
            if not room_data:
                logger.warning(f"房间 {invite_code} 存在但无法获取详细数据")
                return {
                    "success": False,
                    "message": "无法获取房间数据"
                }
                
            try:
                # 其他字段类型转换
                for key in ['total_players', 'spy_count', 'max_rounds', 'speak_time', 'last_words_time']:
                    if key in room_data:
                        try:
                            room_data[key] = int(room_data[key])
                        except (ValueError, TypeError):
                            logger.warning(f"房间 {invite_code} 字段 {key} 类型转换失败: {room_data[key]}")
                            
                if 'is_public' in room_data:
                     room_data['is_public'] = room_data['is_public'].lower() == 'true'
                if 'llm_free' in room_data:
                     room_data['llm_free'] = room_data['llm_free'].lower() == 'true'
                
                # 验证数据
                room = Room(**room_data) 
                room_dict = room.dict() # 使用模型的dict方法确保格式正确
                
                # 直接从 Redis zSet 获取用户 ID
                user_ids_set = await self.redis_client.get_room_users(invite_code)
                user_ids = list(user_ids_set) # 转换为列表方便处理
                
                # 获取并填充完整的用户信息列表
                full_user_list = []
                tasks = [self.user_service.get_user_info(user_id) for user_id in user_ids]
                user_info_results = await asyncio.gather(*tasks)
                
                for i, user_info_result in enumerate(user_info_results):
                    user_id = user_ids[i]
                    if user_info_result["success"]:
                        full_user_list.append(user_info_result["data"])
                    else:
                        logger.warning(f"无法获取房间 {invite_code} 中用户 {user_id} 的信息")
                        full_user_list.append({"id": user_id, "username": f"用户{user_id[:4]}", "avatar_url": "/default_avatar.jpg", "status": "unknown"})

                room_dict['users'] = full_user_list

            except ValidationError as e:
                logger.error(f"从Redis获取的房间 {invite_code} 数据验证失败: {e}")
                logger.error(f"原始数据: {room_data}")
                return {
                    "success": False,
                    "message": "房间数据格式错误"
                }
            except Exception as inner_e:
                logger.error(f"处理房间 {invite_code} 数据时发生内部错误: {inner_e}")
                return {"success": False, "message": "处理房间数据时出错"}

            return {
                "success": True,
                "message": "获取房间详情成功",
                "data": {
                    "room_data": room_dict
                }
            }

        except Exception as e:
            logger.error(f"获取房间 {invite_code} 详情失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取房间详情时出错: {str(e)}"
            }

    async def toggle_user_ready(self, user_id: str, invite_code: str) -> Dict[str, Any]:
        """
        切换用户准备状态

        Args:
            user_id: 用户ID
            invite_code: 房间邀请码

        Returns:
            Dict包含操作结果
        """
        try:
            # 1.检验房间是否存在+房间状态
            room_data = await self.redis_client.get_room_basic_data(invite_code)
            if not room_data or room_data.get("status") != GAME_STATUS_WAITING:
                 message = "房间不存在" if not room_data else f"游戏当前状态为 {room_data.get('status')}，无法更改准备状态"
                 logger.warning(f"toggle_ready 验证失败 (房间: {invite_code}, 用户: {user_id}): {message}")
                 return {"success": False, "message": message}

            # 检查用户是否在房间内
            is_member = await self.redis_client.is_user_in_room(invite_code, user_id)
            if not is_member:
                logger.warning(f"toggle_ready 验证失败: 用户 {user_id} 不在房间 {invite_code} 中。")
                return {"success": False, "message": "您不在此房间内"}

            # 2.修改准备用户集合
            is_currently_ready = await self.redis_client.is_user_ready(invite_code, user_id)

            new_status: bool
            if is_currently_ready:
                # 已准备 -> 取消
                await self.redis_client.remove_user_from_ready_set(invite_code, user_id)
                new_status = False
                
                # 取消准备时，检查是否需要取消倒计时
                if invite_code in self.countdown_tasks:
                    self.countdown_tasks[invite_code].cancel()
                    del self.countdown_tasks[invite_code]
                    
                    # 广播倒计时取消消息
                    if self.websocket_manager:
                        await self.websocket_manager.broadcast_message(
                            invite_code=invite_code, 
                            message={
                                "type": "countdown_cancelled", 
                                "reason": "有玩家取消准备"
                            },
                            is_special=False
                        )
            else:
                # 未准备 -> 准备
                await self.redis_client.add_user_to_ready_set(invite_code, user_id)
                new_status = True

            # 3.广播websocket信息给该房间内所有用户（与前端接收消息格式对应好）
            message = {
                "type": "user_ready",
                "payload": {
                    "user_id": user_id,
                    "is_ready": new_status
                }
            }

            if self.websocket_manager:
                try:
                    # 确保 message_service 可用且能发送广播
                    await self.websocket_manager.broadcast_message(invite_code, message, is_special=False)
                except Exception as ws_err:
                     logger.error(f"用户准备service中广播失败: (房间: {invite_code}): {ws_err}", exc_info=True)
            else:
                logger.warning("用户准备service: WebSocket管理器未配置，无法广播")

            # 4. 如果是准备状态，检查是否所有人都已准备好
            if new_status:
                # 获取房间所有用户和已准备用户
                all_users = await self.redis_client.get_room_users(invite_code)
                ready_users = await self.redis_client.get_room_ready_users(invite_code)
                
                # 检查是否所有人都准备好了（使用集合比较）
                all_users_set = set(all_users)
                if all_users_set and ready_users and all_users_set == ready_users:
                    # 启动游戏开始倒计时
                    await self.start_game_countdown(invite_code)
                    
                    return {
                        "success": True, 
                        "message": "准备状态已切换，所有玩家已准备就绪", 
                        "data": {
                            "is_ready": new_status,
                            "all_ready": True
                        }
                    }

            return {"success": True, "message": "准备状态已切换", "data": {"is_ready": new_status}}

        except Exception as e:
            logger.error(f"toggle_ready 执行出错 (房间: {invite_code}, 用户: {user_id}): {str(e)}", exc_info=True)
            return {"success": False, "message": "处理准备状态时发生服务器内部错误"}
            
    async def start_game_countdown(self, invite_code: str):
        """
        开始游戏倒计时
        
        Args:
            invite_code: 房间邀请码
        """
        logger.info(f"房间 {invite_code} 开始游戏倒计时")
        
        # 如果已有倒计时任务，先取消
        if invite_code in self.countdown_tasks:
            self.countdown_tasks[invite_code].cancel()
            del self.countdown_tasks[invite_code]
            
        # 创建新的倒计时任务
        task = asyncio.create_task(self._countdown_task(invite_code))
        self.countdown_tasks[invite_code] = task
        
        # 设置任务完成回调，清理字典
        def cleanup_task(t):
            self.countdown_tasks.pop(invite_code, None)
            # 检查任务是否有异常但不是取消异常
            if t.done() and not t.cancelled():
                try:
                    t.result()  # 如果有异常会抛出
                except asyncio.CancelledError:
                    pass  # 忽略取消异常
                except Exception as e:
                    logger.error(f"房间 {invite_code} 倒计时任务异常: {e}")
        
        task.add_done_callback(cleanup_task)
            
    async def _countdown_task(self, invite_code: str):
        """
        倒计时任务具体实现
        
        Args:
            invite_code: 房间邀请码

        Notes:
            仅仅是一个实现倒计时的room_service module的内置函数，具体的游戏初始化放到game_service
        """
        try:
            # 倒计时时长（秒）
            countdown_duration = 5
            
            # 广播倒计时开始
            if self.websocket_manager:
                await self.websocket_manager.broadcast_message(
                    invite_code=invite_code,
                    message={
                        "type": "countdown_start", 
                        "duration": countdown_duration
                    },
                    is_special=False
                )
            
            # 等待倒计时结束
            await asyncio.sleep(countdown_duration)

            # 调用GameService开始轮询上帝
            await self.game_service.poll_god_role(invite_code)
            
        except asyncio.CancelledError:
            logger.info(f"房间 {invite_code} 倒计时被取消")
            raise  # 重新抛出异常
        except Exception as e:
            logger.error(f"房间 {invite_code} 倒计时任务发生错误: {str(e)}")
            # 广播错误消息
            if self.websocket_manager:
                await self.websocket_manager.broadcast_message(
                    invite_code=invite_code,
                    message={
                        "type": "game_error",
                        "message": "游戏启动失败，请重试"
                    },
                    is_special=False
                )
            raise  
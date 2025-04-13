"""
services: message_service

Description:
    主要包含和消息直接相关的处理

Notes:
    service层返回统一的格式:
    Dict[str, Any]，包含以下字段：
    - success: bool，操作是否成功
    - message: str，操作结果消息
    - data: Optional[Dict]，返回的数据（如果有）

    - 处理websocket发送过来的消息
    - 服务端的系统消息逻辑
    - 获取房间、secret_channel消息
"""
from typing import Dict, Any, Optional, Set, List
from models.message import Message
from utils.logger_utils import get_logger

logger = get_logger(__name__)

class MessageService:
    def __init__(self, redis_client, websocket_manager):
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager

    async def _validate_message_format(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证消息格式（）"""
        # 验证必要字段
        if not isinstance(message_data, dict):
            return {
                "valid": False,
                "message": "消息必须是JSON对象"
            }
            
        # 验证content字段
        content = message_data.get("content")
        if content is None:
            return {
                "valid": False,
                "message": "消息必须包含content字段"
            }
            
        if not isinstance(content, str) or not content.strip():
            return {
                "valid": False,
                "message": "消息内容不能为空"
            }
            
        # 消息类型验证（如果前端发送type字段）
        msg_type = message_data.get("type")
        if msg_type is not None and msg_type not in ["chat", "secret", "system"]:
            return {
                "valid": False,
                "message": "消息类型无效"
            }
            
        return {
            "valid": True,
            "message": "消息格式有效"
        }

    async def process_message(self, room_id: str, message_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        处理从WebSocket接收到的消息
        
        Args:
            room_id: 房间ID (从WebSocket URL路径中获取)
            message_data: 消息数据 (从WebSocket接收到的JSON数据)
            user_id: 用户ID (已通过WebSocket连接验证)
            
        Returns:
            Dict包含操作结果
        """
        try:
            # 验证消息格式
            validation = await self._validate_message_format(message_data)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"]
                }
            
            # 检查是否是秘密频道消息
            if message_data.get("type") == "secret":
                # 重定向到秘密消息处理
                return await self.process_secret_message(room_id, message_data, user_id)
            
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }

            # 检查用户是否在该房间
            is_user_in_room = await self.redis_client.is_user_in_room(room_id, user_id)
            if not is_user_in_room:
                return {
                    "success": False,
                    "message": "用户不在该房间中"
                }
            
            # 获取用户信息以获取用户名
            user_data = await self.redis_client.get_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "无法获取用户信息"
                }
            
            user_name = user_data.get("username", "未知用户")
            content = message_data.get("content", "")
            
            # 创建消息对象
            message = Message.create_user_message(
                user_id=user_id,
                user_name=user_name,
                content=content
            )
            
            # 将消息存储到Redis
            storage_success = await self.redis_client.add_room_message(room_id, message)
            if not storage_success:
                return {
                    "success": False,
                    "message": "消息存储失败"
                }
            
            # 广播消息到房间
            message_dict = message.dict()
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message=message_dict,
                is_special=False,
                target_users=None
            )
            
            return {
                "success": True,
                "message": "消息发送成功",
                "data": message_dict
            }
            
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"消息处理失败: {str(e)}"
            }
    
    async def process_secret_message(self, room_id: str, message_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        处理秘密频道消息
        
        Args:
            room_id: 房间ID
            message_data: 消息数据
            user_id: 用户ID
            
        Returns:
            Dict包含操作结果
        """
        try:
            # 验证消息格式
            validation = await self._validate_message_format(message_data)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"]
                }
            
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
                
            # 检查用户是否在该房间
            is_user_in_room = await self.redis_client.is_user_in_room(room_id, user_id)
            if not is_user_in_room:
                return {
                    "success": False,
                    "message": "用户不在该房间中"
                }
            
            # 获取用户信息
            user_data = await self.redis_client.get_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "无法获取用户信息"
                }
            
            # 获取目标用户集合
            target_users = message_data.get("target_users", [])
            if not target_users or not isinstance(target_users, list):
                return {
                    "success": False,
                    "message": "秘密消息必须指定目标用户"
                }
            
            # 检查目标用户是否全部在房间内
            for target_id in target_users:
                if not await self.redis_client.is_user_in_room(room_id, target_id):
                    return {
                        "success": False,
                        "message": f"目标用户 {target_id} 不在房间中"
                    }
            
            # 确保发送者也在目标用户列表中（可以看到自己发送的消息）
            if user_id not in target_users:
                target_users.append(user_id)
                
            # 创建消息对象
            user_name = user_data.get("username", "未知用户")
            content = message_data.get("content", "")
            
            message = Message.create_user_message(
                user_id=user_id,
                user_name=user_name,
                content=content
            )
            
            # 存储秘密消息
            storage_success = await self.redis_client.add_secret_channel_message(room_id, message)
            if not storage_success:
                return {
                    "success": False,
                    "message": "秘密消息存储失败"
                }
            
            # 广播到指定用户
            message_dict = message.dict()
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message={**message_dict, "type": "secret"},  # 添加类型标识
                is_special=True,
                target_users=set(target_users)
            )
            
            return {
                "success": True,
                "message": "秘密消息发送成功",
                "data": message_dict
            }
            
        except Exception as e:
            logger.error(f"处理秘密消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"秘密消息处理失败: {str(e)}"
            }
    
    async def send_system_message(self, room_id: str, content: str, target_users: Optional[Set[str]] = None) -> Dict[str, Any]:
        """
        发送系统消息到房间
        
        Args:
            room_id: 房间ID
            content: 系统消息内容
            target_users: 目标用户集合，为None时广播给所有用户
            
        Returns:
            Dict包含操作结果
        """
        try:
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
            
            # 创建系统消息
            message = Message.create_system_message(content=content)
            
            # 将消息存储到Redis
            storage_success = await self.redis_client.add_room_message(room_id, message)
            if not storage_success:
                return {
                    "success": False,
                    "message": "消息存储失败"
                }
            
            # 广播系统消息
            message_dict = message.dict()
            message_dict["type"] = "system"  # 添加类型标识
            
            await self.websocket_manager.broadcast_message(
                room_id=room_id,
                message=message_dict,
                is_special=(target_users is not None),
                target_users=target_users
            )
            
            return {
                "success": True,
                "message": "系统消息发送成功",
                "data": message_dict
            }
            
        except Exception as e:
            logger.error(f"发送系统消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"系统消息发送失败: {str(e)}"
            }
            
    async def get_room_messages(self, room_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        获取房间消息历史
        
        Args:
            room_id: 房间ID
            limit: 获取消息数量限制
            
        Returns:
            Dict包含操作结果和消息列表，消息列表已经保存在字典里，只不过处理需要符合service层的数据规范
        """
        try:
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
                
            # 从Redis获取消息
            messages = await self.redis_client.get_room_messages(room_id, limit)
            
            return {
                "success": True,
                "message": "获取消息成功",
                "data": {
                    "messages": [message.dict() for message in messages]
                }
            }
            
        except Exception as e:
            logger.error(f"获取房间消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"获取消息失败: {str(e)}"
            }
    
    async def get_secret_room_messages(self, room_id: str, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        获取秘密频道消息历史
        
        Args:
            room_id: 房间ID
            user_id: 请求用户ID（用于权限验证）
            limit: 获取消息数量限制
            
        Returns:
            Dict包含操作结果和消息列表，消息列表已经保存在字典里，只不过处理需要符合service层的数据规范
        """
        try:
            # 检查房间是否存在
            room_exists = await self.redis_client.check_room_exists(room_id)
            if not room_exists:
                return {
                    "success": False,
                    "message": "房间不存在"
                }
            
            # 检查用户是否在房间中
            is_user_in_room = await self.redis_client.is_user_in_room(room_id, user_id)
            if not is_user_in_room:
                return {
                    "success": False,
                    "message": "用户不在该房间中"
                }
            
            # 获取秘密频道消息
            messages = await self.redis_client.get_secret_channel_messages(room_id, limit)
            
            # 过滤消息（仅返回与该用户相关的消息）
            # 这里需要根据具体实现来确定如何过滤
            # 暂时以用户ID作为筛选条件，实际可能需要根据target_users等字段判断
            filtered_messages = []
            for message in messages:
                # 如果是该用户发送的消息或发给该用户的消息
                if message.user_id == user_id:
                    filtered_messages.append(message)
                    
            return {
                "success": True,
                "message": "获取秘密频道消息成功",
                "data": {
                    "messages": [message.dict() for message in filtered_messages]
                }
            }
            
        except Exception as e:
            logger.error(f"获取秘密频道消息时出错: {str(e)}")
            return {
                "success": False,
                "message": f"获取秘密频道消息失败: {str(e)}"
            }


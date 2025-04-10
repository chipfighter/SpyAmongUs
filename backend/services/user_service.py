"""
用户服务层

Notes:
    实现一切和用户直接相关的业务逻辑操作
    返回格式统一: Dict[str, Any]，包含以下字段：
    - success: bool，操作是否成功
    - message: str，操作结果消息
    - data: Optional[Dict]，返回的数据（如果有）
"""

from typing import Dict, Any

from models.user import User
from utils.mongo_utils import MongoClient
from utils.redis_utils import RedisClient
from services.auth_service import AuthService
from utils.logger_utils import get_logger
from config import (
    USER_STATUS_ONLINE,
    USER_STATUS_IN_ROOM,
    USER_STATUS_PLAYING
)

logger = get_logger(__name__)

class UserService:
    def __init__(self, redis_client: RedisClient, mongo_client: MongoClient):
        """
        初始化用户服务
        
        Args:
            redis_client: Redis客户端实例
            mongo_client: MongoDB客户端实例
        """
        self.mongo_client = mongo_client
        self.redis_client = redis_client
        self.auth_service = AuthService()
        logger.info("用户服务已初始化")

    async def register_user(self, username: str, password: str) -> Dict[str, Any]:
        """
        注册新用户
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            Dict包含注册结果和相关信息
        """
        try:
            # 检查用户名是否已存在
            existing_user = await self.mongo_client.find_user_by_username(username)
            if existing_user:
                return {
                    "success": False,
                    "message": "用户名已存在"
                }

            # 创建用户对象
            user = User.create_user(username, password)
            
            # 获取完整数据用于MongoDB存储（包含敏感信息，但不包括不需要的字段）
            complete_user_data = {
                **user.dict(),
                "password_hash": user.password_hash,
                "salt": user.salt
            }
            
            # 确保移除MongoDB不需要的字段
            if "current_room" in complete_user_data:
                complete_user_data.pop("current_room")
            
            # 过滤敏感数据用于Redis和返回客户端
            user_dict = user.dict()

            # 保存用户数据到MongoDB（包含敏感信息）
            success = await self.mongo_client.create_user(complete_user_data)
            if success:
                # 缓存用户数据到Redis（不包含敏感信息）
                await self.redis_client.cache_user(user.id, user_dict)

                # 生成访问令牌和刷新令牌
                access_token, refresh_token = self.auth_service.create_tokens(user.id, user.username)

                # 返回用户数据（不包含敏感信息）
                user_dict["access_token"] = access_token
                user_dict["refresh_token"] = refresh_token

                return {
                    "success": True,
                    "message": "注册成功",
                    "data": {
                        "user_id": user.id,
                        "user_data": user_dict
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "注册失败，请稍后重试"
                }

        except Exception as e:
            logger.error(f"注册用户时发生错误: {str(e)}")
            return {
                "success": False,
                "message": "注册过程中发生错误"
            }

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        try:
            # 查找用户
            user_data = await self.mongo_client.find_user_by_username(username)
            if not user_data:
                return {
                    "success": False,
                    "message": "用户不存在"
                }

            # 创建User对象并验证密码
            user = User(**user_data)
            if not user.verify_password(password):
                return {
                    "success": False,
                    "message": "密码错误"
                }

            # 更新用户状态为在线
            user.status = USER_STATUS_ONLINE
            await self.mongo_client.update_user_status(user.id, user.status)

            # 更新Redis缓存（过滤敏感信息）
            user_dict = user.dict()  # 这里会移除敏感字段
            await self.redis_client.cache_user(user.id, user_dict)

            # 生成新的访问令牌和刷新令牌
            access_token, refresh_token = self.auth_service.create_tokens(user.id, user.username)

            # 返回用户数据（不包含敏感信息）
            user_dict["access_token"] = access_token
            user_dict["refresh_token"] = refresh_token

            return {
                "success": True,
                "message": "登录成功",
                "data": user_dict
            }

        except Exception as e:
            logger.error(f"用户登录失败: {str(e)}")
            return {
                "success": False,
                "message": f"登录失败: {str(e)}"
            }

    async def logout(self, user_id: str) -> Dict[str, Any]:
        """用户登出"""
        try:
            # 更新用户状态
            success, message = await self.mongo_client.update_user_status(user_id, "offline")
            if not success:
                return {
                    "success": False,
                    "message": message
                }

            # 从Redis中删除用户缓存
            await self.redis_client.delete_user_cache(user_id)

            return {
                "success": True,
                "message": "登出成功"
            }

        except Exception as e:
            logger.error(f"用户登出失败: {str(e)}")
            return {
                "success": False,
                "message": f"登出失败: {str(e)}"
            }

    async def update_user_status(self, user_id: str, status: str) -> Dict[str, Any]:
        """
        更新用户状态
        
        Args:
            user_id: 用户ID
            status: 新状态 (online/in_room/playing)
        """
        try:
            # 验证状态值
            valid_statuses = [USER_STATUS_ONLINE, USER_STATUS_IN_ROOM, USER_STATUS_PLAYING]
            if status not in valid_statuses and status != "offline":
                return {
                    "success": False,
                    "message": "无效的状态值"
                }

            # 更新MongoDB中的状态
            success, message = await self.mongo_client.update_user_status(user_id, status)
            if not success:
                return {
                    "success": False,
                    "message": message
                }

            # 更新Redis缓存
            user_data = await self.mongo_client.find_user(user_id)
            if user_data:
                await self.redis_client.cache_user(user_id, user_data)

            return {
                "success": True,
                "message": "状态更新成功"
            }

        except Exception as e:
            logger.error(f"更新用户状态失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}"
            }

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户信息"""
        try:
            # 先从Redis缓存中获取
            user_data = await self.redis_client.get_user(user_id)
            if not user_data:
                # 如果缓存中没有，从MongoDB获取
                user_data = await self.mongo_client.find_user(user_id)
                if not user_data:
                    return {
                        "success": False,
                        "message": "用户不存在"
                    }
                    
                # 更新缓存
                await self.redis_client.cache_user(user_id, user_data)

            # 返回用户数据（调用user.dict()去除敏感信息）
            user = User(**user_data)
            return {
                "success": True,
                "message": "获取成功",
                "data": user.dict()
            }

        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取失败: {str(e)}"
            }

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新访问令牌"""
        try:
            # 验证刷新令牌
            new_access_token = self.auth_service.refresh_access_token(refresh_token)
            if not new_access_token:
                return {
                    "success": False,
                    "message": "刷新令牌无效或已过期"
                }

            return {
                "success": True,
                "message": "令牌刷新成功",
                "data": {
                    "access_token": new_access_token
                }
            }

        except Exception as e:
            logger.error(f"刷新令牌失败: {str(e)}")
            return {
                "success": False,
                "message": f"刷新失败: {str(e)}"
            }

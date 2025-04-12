"""
services: user_service

Description:
    实现一切和用户直接相关的业务逻辑操作

Notes:
    返回格式统一:
    Dict[str, Any]，包含以下字段：
    - success: bool，操作是否成功
    - message: str，操作结果消息
    - data: Optional[Dict]，返回的数据（如果有）

    主要功能：
    -

To-Do:
    用户画像+胜率更新
"""

from typing import Dict, Any

from models.user import User, StyleProfile, UserStatistics
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

    async def register(self, username: str, password: str) -> Dict[str, Any]:
        """
        注册新用户

        Notes:
            针对MongoDB和Redis存储的数据需要做区分，先存MongoDB后存redis
            MongoDB不保存时效性高，持久性低的数据
            Redis不保存敏感信息

        Args:
            username: 用户名
            password: 密码
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
            # 不在MongoDB中存储status
            if "status" in complete_user_data:
                complete_user_data.pop("status")
            
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
            if status not in valid_statuses:
                return {
                    "success": False,
                    "message": "无效的状态值"
                }

            # 只更新Redis中的状态
            success = await self.redis_client.update_user_status(user_id, status)
            if not success:
                return {
                    "success": False,
                    "message": "更新状态失败"
                }

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

    async def update_current_room(self, user_id: str, room_id: str = None) -> Dict[str, Any]:
        """更新用户当前所在房间"""
        try:
            # 只在Redis中更新当前房间状态，不持久化到MongoDB
            success = await self.redis_client.update_current_room(user_id, room_id)
            if not success:
                return {
                    "success": False,
                    "message": "更新房间状态失败"
                }

            return {
                "success": True,
                "message": "房间状态已更新"
            }
        except Exception as e:
            logger.error(f"更新用户房间状态失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}"
            }

    async def update_username(self, user_id: str, new_username: str) -> Dict[str, Any]:
        """更新用户名（检查重复）"""
        try:
            # 在MongoDB中更新用户名（已内置重复检查）
            success, message = await self.mongo_client.update_username(user_id, new_username)
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
                "message": "用户名已更新"
            }
        except Exception as e:
            logger.error(f"更新用户名失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}"
            }

    async def update_password(self, user_id: str, old_password: str, new_password: str) -> Dict[str, Any]:
        """更新用户密码"""
        try:
            # 先验证当前密码
            user_data = await self.mongo_client.find_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "用户不存在"
                }

            user = User(**user_data)
            if not user.verify_password(old_password):
                return {
                    "success": False,
                    "message": "当前密码错误"
                }

            # 生成新的密码哈希和盐值
            new_password_hash, new_salt = User.hash_password(new_password)

            # 更新MongoDB中的密码
            success, message = await self.mongo_client.update_password(user_id, new_password_hash, new_salt)
            if not success:
                return {
                    "success": False,
                    "message": message
                }

            return {
                "success": True,
                "message": "密码已更新"
            }
        except Exception as e:
            logger.error(f"更新密码失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}"
            }

    async def update_avatar(self, user_id: str, avatar_url: str) -> Dict[str, Any]:
        """更新用户头像"""
        try:
            # 更新MongoDB中的头像
            success, message = await self.mongo_client.update_avatar(user_id, avatar_url)
            if not success:
                return {
                    "success": False,
                    "message": message
                }

            # 更新Redis缓存
            await self.redis_client.update_avatar(user_id, avatar_url)

            return {
                "success": True,
                "message": "头像已更新"
            }
        except Exception as e:
            logger.error(f"更新用户头像失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}"
            }

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户信息"""
        try:
            # 先从Redis缓存中获取
            user_data = await self.redis_client.get_user(user_id)
            if user_data:
                # 读取出来先重构成对象类型
                # 1. 创建合适的statistics对象
                user_data["statistics"] = UserStatistics(
                    total_games=int(user_data.get("total_games", 0)),
                    win_rates={
                        "civilian": float(user_data.get("win_rate_civilian", 0.0)),
                        "spy": float(user_data.get("win_rate_spy", 0.0))
                    }
                ).dict()

                # 2. 创建合适的style_profile对象
                tags = set()
                if user_data.get("tags"):
                    try:
                        tags = set(user_data.get("tags").split(","))
                    except:
                        pass

                user_data["style_profile"] = StyleProfile(
                    summary=user_data.get("summary", ""),
                    tags=tags,
                    vectors={}
                ).dict()

                # 3. 移除扁平化字段避免冲突
                for key in ["total_games", "win_rate_civilian", "win_rate_spy", "summary", "tags"]:
                    if key in user_data:
                        user_data.pop(key)

                # 如果缓存中没有，从MongoDB获取
                user_data = await self.mongo_client.find_user(user_id)
                if not user_data:
                    return {
                        "success": False,
                        "message": "用户不存在"
                    }
                
                # MongoDB中没有状态字段，设置默认状态
                user_data["status"] = USER_STATUS_ONLINE
                    
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
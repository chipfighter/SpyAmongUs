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

Methods:
    - 注册、登陆、登出
    - 更新当前用户状态、更新用户当前房间、更新用户名、更新用户密码、更新用户头像
    - 获取用户当前信息

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
        """更新用户头像，需要同时更新MongoDB和Redis"""
        try:
            # 更新MongoDB
            success_mongo, message = await self.mongo_client.update_avatar(user_id, avatar_url)
            if not success_mongo:
                return {
                    "success": False,
                    "message": message
                }
            
            # 更新Redis缓存
            success_redis = await self.redis_client.update_avatar(user_id, avatar_url)
            if not success_redis:
                logger.warning(f"更新用户 {user_id} 的头像Redis缓存失败，但不影响主要流程")
            
            return {
                "success": True,
                "message": "头像更新成功"
            }
        except Exception as e:
            logger.error(f"更新用户头像失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新失败: {str(e)}"
            }

    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户常用的基础信息"""
        try:
            # 先从Redis缓存中获取
            user_data = await self.redis_client.get_user(user_id)
            if not user_data:
                # Redis中没有缓存，从MongoDB获取
                user_data = await self.mongo_client.find_user(user_id)
                if not user_data:
                    return {
                        "success": False,
                        "message": "用户不存在"
                    }
                # 缓存到Redis
                await self.redis_client.cache_user(user_id, user_data)
            
            # 提取常用字段
            info = {
                "id": user_id,
                "username": user_data.get("username"),
                "avatar_url": user_data.get("avatar_url"),
                "status": user_data.get("status", USER_STATUS_ONLINE),
                "current_room": user_data.get("current_room"),
                "is_admin": user_data.get("is_admin", False)  # 添加管理员权限字段
            }
            return {
                "success": True,
                "message": "获取成功",
                "data": info
            }
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取用户信息时出错: {str(e)}"
            }

    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户的统计数据（从MongoDB获取）"""
        try:
            # 从MongoDB获取完整的用户信息
            user_data = await self.mongo_client.find_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 提取或创建默认的统计数据
            stats_data = user_data.get("statistics")
            if stats_data and isinstance(stats_data, dict):
                # 使用 Pydantic 模型验证和转换
                stats_obj = UserStatistics(**stats_data)
            else:
                # 如果没有统计数据，返回默认值
                stats_obj = UserStatistics() 
                
            return {
                "success": True,
                "message": "获取统计数据成功",
                "data": stats_obj.dict()
            }

        except Exception as e:
            logger.error(f"获取用户统计数据失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取统计数据时出错: {str(e)}"
            }

    async def get_user_style_profile(self, user_id: str) -> Dict[str, Any]:
        """获取用户的画像数据（从MongoDB获取）"""
        try:
            # 从MongoDB获取完整的用户信息
            user_data = await self.mongo_client.find_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
                
            # 提取或创建默认的画像数据
            profile_data = user_data.get("style_profile")
            if profile_data and isinstance(profile_data, dict):
                # 处理 tags 从 list (MongoDB存储) 到 set (Pydantic模型)
                if "tags" in profile_data and isinstance(profile_data["tags"], list):
                    profile_data["tags"] = set(profile_data["tags"])
                elif "tags" not in profile_data:
                     profile_data["tags"] = set()
                
                # 确保 vectors 存在
                if "vectors" not in profile_data:
                    profile_data["vectors"] = {}
                    
                # 使用 Pydantic 模型验证和转换
                profile_obj = StyleProfile(**profile_data)
            else:
                # 如果没有画像数据，返回默认值
                profile_obj = StyleProfile()
                
            return {
                "success": True,
                "message": "获取用户画像成功",
                "data": profile_obj.dict()
            }

        except Exception as e:
            logger.error(f"获取用户画像数据失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取用户画像时出错: {str(e)}"
            }
            
    async def update_game_statistics(self, user_id: str, game_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新用户游戏统计数据
        
        Args:
            user_id: 用户ID
            game_result: 游戏结果数据，包含:
                - role: 用户角色 ('civilian' 或 'spy')
                - win: 是否获胜 (bool)
        """
        try:
            # 从MongoDB获取当前用户统计数据
            user_data = await self.mongo_client.find_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 获取当前统计数据
            current_stats = user_data.get("statistics", {})
            if not current_stats:
                current_stats = UserStatistics().dict()
            
            # 提取游戏结果
            role = game_result.get("role", "civilian")
            is_win = game_result.get("win", False)
            
            # 更新总游戏数据
            current_stats["total_games"] = current_stats.get("total_games", 0) + 1
            
            if is_win:
                current_stats["win_count"] = current_stats.get("win_count", 0) + 1
            
            # 计算总胜率
            if current_stats["total_games"] > 0:
                current_stats["win_rate"] = round(current_stats["win_count"] / current_stats["total_games"], 3)
            
            # 更新角色特定数据
            if role == "civilian":
                current_stats["civilian_games"] = current_stats.get("civilian_games", 0) + 1
                if is_win:
                    current_stats["civilian_wins"] = current_stats.get("civilian_wins", 0) + 1
                
                # 计算平民胜率
                if current_stats["civilian_games"] > 0:
                    current_stats["civilian_win_rate"] = round(
                        current_stats["civilian_wins"] / current_stats["civilian_games"], 3
                    )
                    # 同时更新兼容旧版本的win_rates字典
                    if "win_rates" not in current_stats:
                        current_stats["win_rates"] = {}
                    current_stats["win_rates"]["civilian"] = current_stats["civilian_win_rate"]
                    
            elif role == "spy":
                current_stats["spy_games"] = current_stats.get("spy_games", 0) + 1
                if is_win:
                    current_stats["spy_wins"] = current_stats.get("spy_wins", 0) + 1
                
                # 计算卧底胜率
                if current_stats["spy_games"] > 0:
                    current_stats["spy_win_rate"] = round(
                        current_stats["spy_wins"] / current_stats["spy_games"], 3
                    )
                    # 同时更新兼容旧版本的win_rates字典
                    if "win_rates" not in current_stats:
                        current_stats["win_rates"] = {}
                    current_stats["win_rates"]["spy"] = current_stats["spy_win_rate"]
            
            # 更新MongoDB中的统计数据
            success, message = await self.mongo_client.update_user_statistics(user_id, current_stats)
            if not success:
                return {
                    "success": False,
                    "message": message
                }
            
            # 如果用户在Redis中有缓存，也更新缓存
            user_cached = await self.redis_client.user_exists(user_id)
            if user_cached:
                # 获取最新的用户数据并更新缓存
                updated_user_data = await self.mongo_client.find_user(user_id)
                if updated_user_data:
                    await self.redis_client.cache_user(user_id, updated_user_data)
            
            return {
                "success": True,
                "message": "游戏统计数据已更新",
                "data": current_stats
            }
        
        except Exception as e:
            logger.error(f"更新用户游戏统计数据失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新统计数据时出错: {str(e)}"
            }

    async def update_user_points(self, user_id: str, points_delta: int) -> Dict[str, Any]:
        """
        更新用户积分
        
        Args:
            user_id: 用户ID
            points_delta: 积分变化值，可正可负
        """
        try:
            # 从MongoDB获取当前用户数据
            user_data = await self.mongo_client.find_user(user_id)
            if not user_data:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 获取当前积分
            current_points = user_data.get("points", 0)
            
            # 计算新积分（确保不为负）
            new_points = max(0, current_points + points_delta)
            
            # 更新MongoDB中的积分
            result = await self.mongo_client.db.users.update_one(
                {"id": user_id},
                {"$set": {"points": new_points}}
            )
            
            if result.matched_count == 0:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 如果用户在Redis中有缓存，也更新缓存
            user_cached = await self.redis_client.user_exists(user_id)
            if user_cached:
                await self.redis_client.hset(f"user:{user_id}", "points", str(new_points))
            
            return {
                "success": True,
                "message": "用户积分已更新",
                "data": {
                    "previous_points": current_points,
                    "new_points": new_points,
                    "delta": points_delta
                }
            }
        
        except Exception as e:
            logger.error(f"更新用户积分失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新积分时出错: {str(e)}"
            }

    async def toggle_user_admin_status(self, user_id: str, is_admin: bool) -> Dict[str, Any]:
        """
        设置或取消用户的管理员状态
        
        Args:
            user_id: 用户ID
            is_admin: 是否设为管理员
        """
        try:
            # 更新MongoDB中的管理员状态
            result = await self.mongo_client.db.users.update_one(
                {"id": user_id},
                {"$set": {"is_admin": is_admin}}
            )
            
            if result.matched_count == 0:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 如果用户在Redis中有缓存，也更新缓存
            user_cached = await self.redis_client.user_exists(user_id)
            if user_cached:
                await self.redis_client.hset(f"user:{user_id}", "is_admin", str(is_admin).lower())
            
            action = "设为管理员" if is_admin else "取消管理员权限"
            return {
                "success": True,
                "message": f"用户已{action}",
                "data": {
                    "user_id": user_id,
                    "is_admin": is_admin
                }
            }
        
        except Exception as e:
            logger.error(f"更新用户管理员状态失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新管理员状态时出错: {str(e)}"
            }

    async def set_user_mute_status(self, user_id: str, is_muted: bool, mute_until: int = 0) -> Dict[str, Any]:
        """
        设置用户禁言状态
        
        Args:
            user_id: 用户ID
            is_muted: 是否禁言
            mute_until: 禁言截止时间戳（秒），0表示永久禁言
        """
        try:
            # 如果取消禁言，则将禁言时间重置为0
            if not is_muted:
                mute_until = 0
            
            # 更新MongoDB中的禁言状态
            result = await self.mongo_client.db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "is_muted": is_muted,
                    "mute_until": mute_until
                }}
            )
            
            if result.matched_count == 0:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 如果用户在Redis中有缓存，也更新缓存
            user_cached = await self.redis_client.user_exists(user_id)
            if user_cached:
                await self.redis_client.hset(f"user:{user_id}", "is_muted", str(is_muted).lower())
                await self.redis_client.hset(f"user:{user_id}", "mute_until", str(mute_until))
            
            action = "已禁言" if is_muted else "已解除禁言"
            return {
                "success": True,
                "message": f"用户{action}",
                "data": {
                    "user_id": user_id,
                    "is_muted": is_muted,
                    "mute_until": mute_until
                }
            }
        
        except Exception as e:
            logger.error(f"更新用户禁言状态失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新禁言状态时出错: {str(e)}"
            }

    async def set_user_ban_status(self, user_id: str, is_banned: bool, ban_until: int = 0) -> Dict[str, Any]:
        """
        设置用户禁止行为状态
        
        Args:
            user_id: 用户ID
            is_banned: 是否禁止行为
            ban_until: 禁止行为截止时间戳（秒），0表示永久禁止
        """
        try:
            # 如果取消禁止行为，则将禁止时间重置为0
            if not is_banned:
                ban_until = 0
            
            # 更新MongoDB中的禁止行为状态
            result = await self.mongo_client.db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "is_banned": is_banned,
                    "ban_until": ban_until
                }}
            )
            
            if result.matched_count == 0:
                return {
                    "success": False,
                    "message": "用户不存在"
                }
            
            # 如果用户在Redis中有缓存，也更新缓存
            user_cached = await self.redis_client.user_exists(user_id)
            if user_cached:
                await self.redis_client.hset(f"user:{user_id}", "is_banned", str(is_banned).lower())
                await self.redis_client.hset(f"user:{user_id}", "ban_until", str(ban_until))
            
            action = "已禁止行为" if is_banned else "已解除禁止行为"
            return {
                "success": True,
                "message": f"用户{action}",
                "data": {
                    "user_id": user_id,
                    "is_banned": is_banned,
                    "ban_until": ban_until
                }
            }
        
        except Exception as e:
            logger.error(f"更新用户禁止行为状态失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新禁止行为状态时出错: {str(e)}"
            }